// include/strata/core/deterministic.hpp - the deterministic mode (--deterministic, STRATA_DETERMINISTIC=1; opt-in).
//
// Off by default, and then nothing changes.  On, every choice that the engine otherwise takes from a clock or from
// whether an asynchronous copy has landed is taken from the data and the step counters instead, so a greedy answer
// is the same bytes from one start to the next on the same machine and settings (docs/DETAILS.md, "Deterministic
// mode"): the verify window's size is priced by a fixed cost shape instead of measured round times (DraftPolicy),
// the PCIe share is not refined from the CPU pool's timing (PcieAuto) and its probe is rounded to a 0.05 step, the
// measured prompt CPU share is off (a fixed STRATA_PREFILL_CPU_SHARE=x is kept), an automatic expert cache is cut to
// a whole number of 512 MiB, and the timing-gated opt-ins (STRATA_ADAPT_NOWAIT, --adapt-async, --pipeline-windows)
// take their step-counted forms.
#pragma once

#include <atomic>
#include <cstdlib>

namespace strata::core {

inline std::atomic<int>& deterministic_state() {
    static std::atomic<int> v{-1};   // -1: not read yet
    return v;
}

/// The mode is on: --deterministic was given, or STRATA_DETERMINISTIC is set to something other than 0.
inline bool deterministic() {
    int v = deterministic_state().load(std::memory_order_relaxed);
    if (v < 0) {
        const char* e = std::getenv("STRATA_DETERMINISTIC");
        v = e != nullptr && e[0] != '\0' && !(e[0] == '0' && e[1] == '\0') ? 1 : 0;
        deterministic_state().store(v, std::memory_order_relaxed);
    }
    return v > 0;
}

/// --deterministic: set once while the command line is read, before anything asks.
inline void set_deterministic(bool on) { deterministic_state().store(on ? 1 : 0, std::memory_order_relaxed); }

}  // namespace strata::core
