"""Regression test for M13: subagent failure bails out fast.

The pattern now matches subagent_review.py: ``wait(..., FIRST_EXCEPTION)``
returns as soon as any future raises, then ``shutdown(wait=False,
cancel_futures=True)`` bails out. The slow agent should be cancelled
rather than waited on.
"""
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_EXCEPTION

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _fast_ok():
    return "ok"


def _slow_then_fail():
    time.sleep(0.5)
    raise RuntimeError("slow subagent failed")


def _very_slow_ok():
    time.sleep(2.0)
    return "slow_ok"


def test_failure_bails_fast():
    """When one subagent fails, we should NOT wait for the slow one to
    finish. Upper bound: well under the slow task's 2.0s duration."""
    start = time.time()
    first_failure = None
    pool = ThreadPoolExecutor(max_workers=3)
    try:
        futures = {
            pool.submit(_fast_ok): "fast",
            pool.submit(_slow_then_fail): "fail",
            pool.submit(_very_slow_ok): "slow",
        }
        done, not_done = wait(futures, return_when=FIRST_EXCEPTION)
        for f in done:
            try:
                f.result()
            except Exception as exc:
                if first_failure is None:
                    first_failure = exc
        for f in not_done:
            f.cancel()
    finally:
        if first_failure is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        else:
            pool.shutdown(wait=True)

    elapsed = time.time() - start
    assert first_failure is not None, "test setup: expected a failure"
    # Failing task sleeps 0.5s, so wait returns ~0.5s.
    # slow_ok (2.0s) should be cancelled — if waited on, elapsed >= 2.0.
    assert elapsed < 1.5, (
        f"failure path took {elapsed:.2f}s, expected < 1.5s. "
        f"slow subagent was probably waited on instead of cancelled."
    )
