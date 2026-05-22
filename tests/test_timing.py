"""
Timing loop performance tests.

Run: python tests/test_timing.py
Tests sleep accuracy and loop Hz variability at 50 Hz (main.py default).
"""

import ctypes
import statistics
import sys
import time

RATE_HZ = 50
PERIOD = 1.0 / RATE_HZ
DURATION_S = 2.0
N_ITERS = int(DURATION_S * RATE_HZ)


def _enable_winmm():
    if sys.platform == "win32":
        dll = ctypes.WinDLL("winmm")
        dll.timeBeginPeriod(1)
        return dll
    return None


def _disable_winmm(dll):
    if dll:
        dll.timeEndPeriod(1)


def _run_loop(use_winmm: bool) -> list[float]:
    """Run the same timing pattern as main.py; return per-iteration durations (s)."""
    dll = _enable_winmm() if use_winmm else None
    durations = []
    next_time = time.monotonic()
    try:
        for _ in range(N_ITERS):
            t0 = time.monotonic()
            # simulate ~0.5 ms of work (NiDAQ read + pack)
            time.sleep(0.0005)
            next_time += PERIOD
            sleep_for = next_time - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_time = time.monotonic()
            durations.append(time.monotonic() - t0)
    finally:
        _disable_winmm(dll)
    return durations


def _stats(label: str, durations: list[float]):
    hz = [1.0 / d for d in durations]
    mean_hz = statistics.mean(hz)
    stdev_hz = statistics.stdev(hz)
    min_hz = min(hz)
    max_hz = max(hz)
    late = sum(1 for d in durations if d > PERIOD * 1.5)
    print(f"\n{label}")
    print(f"  mean  {mean_hz:6.1f} Hz   stdev {stdev_hz:5.2f} Hz")
    print(f"  range [{min_hz:.1f}, {max_hz:.1f}] Hz")
    print(f"  late iterations (>1.5× period): {late}/{N_ITERS}")


def test_sleep_overshoot():
    """Measure how much time.sleep() overshoots its target."""
    dll = _enable_winmm()
    overshoots_ms = []
    try:
        for target_ms in [1, 2, 5, 10, 20]:
            target_s = target_ms / 1000.0
            samples = []
            for _ in range(50):
                t0 = time.monotonic()
                time.sleep(target_s)
                samples.append((time.monotonic() - t0 - target_s) * 1000)
            mean_over = statistics.mean(samples)
            stdev_over = statistics.stdev(samples)
            overshoots_ms.append(mean_over)
            print(f"  sleep({target_ms:2d} ms): mean overshoot {mean_over:+.3f} ms  stdev {stdev_over:.3f} ms")
    finally:
        _disable_winmm(dll)
    return overshoots_ms


def test_loop_variability():
    print(f"\n--- Loop variability at {RATE_HZ} Hz over {DURATION_S} s ({N_ITERS} iters) ---")
    without = _run_loop(use_winmm=False)
    _stats("Without WinMM timer", without)
    with_ = _run_loop(use_winmm=True)
    _stats("With WinMM timeBeginPeriod(1)", with_)


def test_debug_window_noise():
    """Show how the 0.1 s debug window in main.py amplifies apparent Hz jitter."""
    dll = _enable_winmm()
    print("\n--- Debug window noise (simulating main.py's 0.1 s print interval) ---")
    print("  Samples per window | apparent Hz stdev")
    try:
        for window_s in [0.1, 0.5, 1.0, 2.0]:
            durations = _run_loop(use_winmm=True)
            window_counts = []
            acc = 0.0
            count = 0
            for d in durations:
                acc += d
                count += 1
                if acc >= window_s:
                    window_counts.append(count / acc)
                    acc = 0.0
                    count = 0
            if len(window_counts) > 1:
                stdev = statistics.stdev(window_counts)
                samples = int(window_s * RATE_HZ)
                print(f"  {window_s:.1f} s (~{samples:3d} samples): stdev {stdev:.2f} Hz")
    finally:
        _disable_winmm(dll)


if __name__ == "__main__":
    print("=== Sleep overshoot ===")
    test_sleep_overshoot()
    test_loop_variability()
    test_debug_window_noise()
    print("\nDone.")
