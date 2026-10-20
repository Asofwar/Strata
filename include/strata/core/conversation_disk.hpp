// The disk tier of --serve's parked conversations (--conversation-disk-dir): the RAM cache's evictions
// (ConversationCache::set_on_evict) are written to session files (conversation_file.hpp, one per layer-split stage)
// by a background thread and read back when a request continues them, within a time limit and a byte budget.
// By default only this process reads its files back, and the folder's files of this tier are removed at start and at
// the end.  `persist`: the files are bound to the session files' identity (model and settings) instead, a small index
// file beside each conversation lists its tokens, and the next start picks them up (no time limit, the budget only).
#pragma once

#include "strata/core/conversation_cache.hpp"
#include "strata/core/conversation_file.hpp"

#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <functional>
#include <mutex>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

namespace strata::core {

struct ConversationDiskOptions {
    std::string dir;                 ///< empty: the tier is off
    uint64_t budget_bytes = 0;       ///< at most this many bytes of files; 0: off
    uint64_t min_free_bytes = 0;     ///< a write needs the file plus this much free on the disk (session preflight)
    bool persist = false;            ///< keep the files for later runs, bound to `identity`
    SessionFileIdentity identity;    ///< persist: the session files' identity (model and settings fingerprints)
    /// Called with every diagnostic line (no trailing newline), from the caller's or the writer's thread.
    std::function<void(const std::string&)> log;
    /// Tests: called on the writer thread before each write starts.
    std::function<void()> before_write;
};

/// What the tier did since it started (diagnostics).
struct ConversationDiskStats {
    size_t queued = 0, written = 0, write_failed = 0, ram_hits = 0, disk_hits = 0, read_failed = 0;
    size_t streamed_writes = 0, streamed_reads = 0;   ///< write_now / take_stream (no RAM image)
    size_t evicted = 0, waits = 0;
    uint64_t bytes_written = 0, bytes_read = 0;
    uint64_t tokens_back = 0;                 ///< prompt tokens given back (not read again) by ram or disk hits
    double write_ms = 0, read_ms = 0, wait_ms = 0;
};

class ConversationDiskTier {
public:
    explicit ConversationDiskTier(ConversationDiskOptions options);
    ~ConversationDiskTier();
    ConversationDiskTier(const ConversationDiskTier&) = delete;
    ConversationDiskTier& operator=(const ConversationDiskTier&) = delete;

    bool enabled() const { return open_; }
    bool persistent() const { return open_ && options_.persist; }
    /// Creates the folder (0700 on POSIX) and starts the writer.  This tier's files a previous run left there are
    /// removed, or with `persist` taken in when their identity matches (the others removed).  False (and the tier
    /// stays off) when the folder cannot be used.
    bool open(std::string& error);

    /// Queues `image` for the writer; its RAM is freed when its write ends, stored or not.  Every checkpoint is written
    /// with it (they hold no K/V), so a prompt that leaves the conversation early still resumes from one.  False when
    /// the tier is off or over budget.
    bool put(SavedConversation&& image);

    struct Match {
        uint64_t id = 0;        ///< the entry (stable while the writer runs; 0 = none)
        int64_t tokens = 0;
        bool live = false;
        uint64_t bytes = 0;     ///< the entry's files (queued: the image's estimate)
        bool queued = false;    ///< still in RAM: take() hands it back without reading a file
        int64_t length = 0;     ///< the entry's live tokens (a checkpoint match restores the whole entry)
        size_t checkpoints = 0; ///< how many checkpoints it holds (a streamed read keeps them and the live state in RAM)
    };
    /// The longest prefix of `prompt` an entry holds (its live state or its checkpoint), queued or on the disk, as
    /// ConversationCache::best; ties prefer the newest entry.
    template<class Token>
    Match best(const std::vector<Token>& prompt, const std::vector<ConversationImageKey>& images, bool cvec) const {
        std::lock_guard<std::mutex> lock(m_);
        Match best;
        auto scan = [&](const Entry& e, bool queued) {
            if (e.cvec != cvec) return;
            auto consider = [&](const ConversationCheckpoint& c, bool live) {
                const int64_t n = conversation_prefix(c, prompt, images);
                if (n > best.tokens || (n == best.tokens && n > 0 && e.id > best.id))
                    best = {e.id, n, live, e.bytes, queued, (int64_t) e.live.ids.size(), e.checkpoints.size()};
            };
            consider(e.live, true);
            for (const auto& c : e.checkpoints) consider(c, false);
        };
        for (const auto& e : entries_) scan(e, false);
        for (const auto& j : queue_) scan(j.entry, true);
        if (writing_) scan(writing_entry_, false);   // its file appears when the write ends: take() waits for it
        return best;
    }

    /// Hands entry `id` back in `out` (its stage images included) and removes it from the tier either way: from RAM
    /// when it is still queued, else from the disk (waiting for its write when it is being written).  `admit(need,
    /// why)` is asked before each file's payload is allocated (session_file_read's RAM preflight).  `tokens` is what
    /// the request reuses (diagnostics).  On failure `out` is empty and `error` says why.
    bool take(uint64_t id, int64_t tokens, SavedConversation& out, std::string& error,
              const std::function<bool(uint64_t need_bytes, std::string& why)>& admit = {});

    /// Streamed park (when RAM cannot hold the image): writes `meta` (everything but the K/V) with its K/V pulled
    /// from `kv` straight into the file, on the caller's thread, and adds the entry.  `estimate` (the file's size,
    /// about) makes room under the budget first.  A single-stage image only.  False when the tier is off, the image
    /// is over the budget or the write failed (`error`); nothing is left on the disk then.
    bool write_now(const SavedConversation& meta, const std::vector<SessionKvSource>& kv, uint64_t estimate,
                   std::string& error);
    /// Streamed read (when RAM cannot hold the image): as take(), but the K/V goes to `sink` as it is read and `meta`
    /// gets the rest (meta.kv: headers only).  A single-stage entry on the disk only (not queued: take() hands those
    /// back from RAM).  The entry leaves the tier either way.  `sink.wrote` says whether the K/V reached the sink.
    /// `limits`: the reader's bounds (geometry, tokens, checkpoints, state sizes); its kv_sink is set here.
    bool take_stream(uint64_t id, int64_t tokens, SessionKvSink& sink, SavedConversation& meta, std::string& error,
                     const SessionReadLimits& limits = {});
    /// Keeps entry `id` out of the budget's evictions until take()/take_stream() takes it or unguard(): the file a
    /// request will stream in once the outgoing conversation is parked, which that park's write must not remove.
    void guard(uint64_t id);
    void unguard();
    /// The number of files entry `id` is in (0: not on the disk, or queued / being written).
    size_t files_of(uint64_t id) const;

    /// Whether images wait in the queue or are being written (their RAM is not back yet).
    bool pending() const;
    /// Blocks until the queue is empty and no write runs; returns the ms it waited.
    double wait_idle();
    /// #879: every conversation goes - queued, being written (waited for) and on the disk, files too.  Returns how many.
    size_t clear();

    size_t size() const;                    ///< entries on the disk
    uint64_t bytes() const;                 ///< their files' bytes
    ConversationDiskStats stats() const;
    /// One line of totals for the log.
    std::string summary() const;
    /// The file name prefix of this tier (tests).
    static const char* file_prefix() { return "strata-conv-"; }

private:
    struct Entry {
        uint64_t id = 0;
        std::vector<std::string> files;          ///< the first stage's image, then one per later stage
        ConversationCheckpoint live;             ///< ids and images only: what best() matches
        std::vector<ConversationCheckpoint> checkpoints;
        bool cvec = true;
        uint64_t bytes = 0;                      ///< the files' bytes (queued: the image's estimate)
        std::string index;                       ///< persist: the index file
        int64_t written_s = 0;                   ///< persist: when it was written (seconds since the epoch)
    };
    struct Job {
        Entry entry;
        SavedConversation image;
    };
    void writer();
    void write(Job& job);                                    // without the lock
    // m_ held: oldest out (not the guarded one) until `incoming` fits beside the files and the writes in flight
    void make_room_locked(uint64_t incoming, size_t& removed);
    std::string file_name(uint64_t id, size_t stage) const;
    void remove_locked(size_t index, bool delete_files);     // m_ held
    void log(const std::string& line) const;
    SessionFileIdentity file_identity() const;
    bool write_index(Entry& e, std::string& error) const;
    bool read_index(const std::string& path, Entry& e) const;
    std::string scan_folder(size_t& stale, std::error_code& ec);   // open(): take in or remove; its log part

    ConversationDiskOptions options_;
    bool open_ = false;
    uint64_t nonce_ = 0, next_id_ = 0, bytes_ = 0;
    uint64_t inflight_ = 0;       ///< the writes under way (the writer's and write_now's), counted against the budget
    uint64_t guarded_ = 0;        ///< guard(): the entry the budget does not evict
    mutable std::mutex m_;
    std::condition_variable cv_;
    std::deque<Entry> entries_;   ///< on the disk, oldest first
    std::deque<Job> queue_;       ///< waiting for the writer, oldest first
    bool writing_ = false;        ///< the writer holds a job (writing_entry_ is its keys)
    Entry writing_entry_;
    bool stop_ = false;
    std::thread thread_;
    ConversationDiskStats stats_;
};

}  // namespace strata::core
