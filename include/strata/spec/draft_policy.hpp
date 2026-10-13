// include/strata/spec/draft_policy.hpp - per verify round: the MTP's window, or a lookup (suffix) window?
//
// The suffix drafter (prompt lookup) proposes the tokens that followed an earlier repeat of the context. Taken
// whenever it proposes more than the MTP, it lost 2-8% on ordinary text: a long lookup window costs much more to
// verify than the MTP's usual 3-4 tokens, and it is only worth that when enough of it is accepted. llama.cpp's
// lookup decoding answers the same problem with confidence thresholds on its n-gram statistics; here the policy
// learns both sides online and compares expected committed tokens per millisecond:
//
//   MTP     E = the mean tokens a window of that size has committed (EMA), at the measured cost of that size
//   lookup  E(k) = 1 + q + q^2 + ... + q^k for k <= the proposal, q = the acceptance rate of lookup drafts whose
//           match was about as long (4 buckets of match length, decayed counts), at the measured cost of k + 1
//
// and takes the lookup window only when its best E/cost beats the MTP's by `margin`. Costs are the measured round
// times per window size (EMA; sizes not seen yet are scaled from seen ones by a prior shape), so the policy adapts
// to the machine and the context length. It only chooses which drafts to verify: the output is unchanged.
#pragma once

#include <array>
#include <cstdint>

namespace strata::spec {

class DraftPolicy {
public:
    static constexpr int kMaxT = 8;
    static constexpr int kBuckets = 4;

    explicit DraftPolicy(int max_t, double margin = 0.03);

    struct Pick {
        bool lookup = false;
        int t = 1;                      // window size (1 + drafts)
    };
    /// `t_mtp`: the MTP's window; `lookup_k`: the lookup proposal's length (0 = none); `match`: its match length.
    Pick choose(int t_mtp, int lookup_k, int match) const;
    /// After the round: the window it used, the drafts accepted, and the round's time (verify + commit + draft).
    void observe(bool lookup, int t, int accepted, int match, double round_ms);

    /// --lookup-chain: how many of `k_avail` lookup tokens to append after an MTP window of `t_mtp` tokens whose
    /// drafts all hold with probability `p_mtp` (estimated from the draft layer's own probabilities): the k with the
    /// best expected tokens per ms, E(t_mtp) + p_mtp (c + c^2 + .. + c^k) at the cost of t_mtp + k, if it beats the MTP
    /// window alone by `margin`; c = the acceptance of chained drafts by match length (their own counts). 0 = none.
    int chain(int t_mtp, double p_mtp, int k_avail, int match) const;
    /// After a chained round: the MTP window's size, the chained tokens, the window's accepted drafts, its time.
    void observe_chain(int t_mtp, int k, int accepted, int match, double round_ms);
    double chain_rate(int match) const;
    double lookup_rate(int match) const;   // current q for a match length
    double cost_ms(int t) const;           // measured or scaled round time of a window of t tokens

private:
    static int bucket(int match);
    double mtp_tokens(int t) const;
    bool stale(int t) const;               // a size not measured for a long stretch of rounds

    int max_t_;
    double margin_;
    std::array<double, kMaxT + 1> cost_{}, cost_n_{};      // round ms by window size
    std::array<double, kMaxT + 1> mtp_tok_{}, mtp_n_{};    // tokens committed by MTP windows of that size
    std::array<double, kBuckets> ok_{}, bad_{};            // lookup drafts accepted / windows cut short, decayed
    std::array<double, kBuckets> cok_{}, cbad_{};          // chained lookup drafts, the same (reached rounds only)
    double rounds_ = 0;                                    // rounds observed so far
    std::array<double, kMaxT + 1> last_{};                 // the round at which each size was last measured
};

// --spec-adaptive MIN[:MAX] (opt-in): the MTP's window cap per round, picked in [MIN, MAX] for the most committed
// tokens per ms.  A round run under cap c with window t (t <= c; --spec-min-p and the context's end can shorten it)
// that accepted a drafts also tells what every smaller cap d would have done: its window min(t, d) and min(a + 1, d)
// tokens (the drafts are a chain, so a shorter one is the same prefix).  So for each cap the policy keeps
//   tok(d)    EMA of the tokens a round under cap d commits (counterfactual for d below the cap used)
//   w(d, u)   EMA of how often cap d's window is u tokens
// (both as sums that fade by `kDecay` every round, so a cap seen only in a few recent rounds is judged by those) and
// the measured round time per window size (EMA; sizes not measured yet: linear in the measured ones), and moves to
// the d with the best tok(d) / sum_u w(d, u) cost(u) when it beats the current cap's by `margin`.  A cap above the
// one in use has no counterfactual: every `probe` rounds one round runs at cap + 1 (and, alternately, cap - 1 to
// measure the smaller window's cost); next to the best cap that costs little.  Like DraftPolicy it only chooses how
// many drafts to verify; the verify window decides every token.
class SpecDepth {
public:
    static constexpr int kMaxT = DraftPolicy::kMaxT;

    static constexpr double kDecay = 0.98;   // per round: a sample's weight halves in ~35 rounds

    SpecDepth(int min_t, int max_t, int probe = 8, double margin = 0.02);

    /// The cap for the next round (its drafts: next() - 1).
    int next();
    /// After a round: the cap it ran under, its window, the drafts accepted and the round's time.
    void observe(int cap, int t, int accepted, double round_ms);

    int current() const { return cur_; }
    int min_t() const { return min_; }
    int max_t() const { return max_; }
    double tokens(int d) const;                  // tok(d) (0 = no data yet)
    double cost_ms(int t) const;
    double score(int d) const;                   // tok(d) / expected cost under cap d (0 = no data yet)
    int64_t rounds_at(int d) const { return used_[(size_t) d]; }
    int switches() const { return switches_; }

private:
    int min_, max_, probe_;
    double margin_;
    int cur_;
    int64_t since_probe_ = 0;
    bool probe_up_ = true;
    int switches_ = 0;
    std::array<double, kMaxT + 1> tok_s_{}, tok_w_{};      // faded sums: tokens, rounds
    std::array<std::array<double, kMaxT + 1>, kMaxT + 1> w_{};
    std::array<double, kMaxT + 1> cost_{}, cost_n_{};
    std::array<int64_t, kMaxT + 1> used_{};
};

}  // namespace strata::spec
