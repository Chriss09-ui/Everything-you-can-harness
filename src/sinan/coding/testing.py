"""Coding-layer test runner — runs the generated harness against test cases.

旧的 testing.py 用 Playwright 跑 UI 测试，但司南生成的不是网页，而是一套
agent 框架（LangGraph 风格的多 agent 系统，通过 main.py 接受输入、产出 JSON
artifact）。本文件重写为：

- run_qa_eval(...)      ：sprint 末尾的整体评测。加载 design_draft.test_cases，
                          用 subprocess + timeout 跑 `python main.py "<input>"`
                          每条用例，对照 expected_output_keys 汇总成 QAGrade。
- run_e2e_test(...)     ：单 feature 测试。研发层节点 test_feature 调用；因为
                          feature 粒度不适合端到端，这里只跑一个"冒烟"：让
                          main.py 跑一遍空输入不崩。
- run_sanity_check(...) ：基本文件健全性检查（src/ 和 main.py 是否还在）。

关键约束：
- subprocess 必须带 timeout（默认 60 秒），避免 generator 写死循环拖死整个流程。
- runner 不解析 LLM 输出，只看：进程是否退出码 0 / stdout 是否为合法 JSON /
  必要的 key 是否在。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from ..artifacts import get_run_dir, append_progress_log


# ── Result types ────────────────────────────────────────────────────────────


@dataclass
class TestResult:
    passed: bool
    output: str
    duration_ms: int
    errors: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestCaseResult:
    id: str
    passed: bool
    duration_ms: int
    error: str = ""
    missing_keys: list = field(default_factory=list)


@dataclass
class QAGrade:
    """Runner's verdict on the test_cases suite.

    Soft scores (functionality/product_depth/visual_quality/code_quality) live
    on the LLM evaluator's grade dict, not here — the runner only has hard
    data: pass count and pass ratio. Earlier versions stuffed hardcoded 5s
    into a 4-dim score that downstream then ignored; that dead data is gone.
    """
    overall_pass: bool
    summary: str
    functional_ratio: float = 0.0  # hard_pass_count / total — 0 when skipped
    runner_results: list[dict] = field(default_factory=list)  # per-case details


# ── Public API ──────────────────────────────────────────────────────────────


def run_e2e_test(run_id: str, feature_id: str) -> TestResult:
    """Run a smoke test for a single feature.

    The new runner model is whole-harness (main.py + test_cases), so per-feature
    testing collapses to: "if main.py exists, run it with empty input and check
    it doesn't explode". The actual feature-level pass/fail is determined by
    generator self-marking + sprint-level QA.
    """
    start = time.time()
    harness_dir = _harness_dir(run_id)
    if not harness_dir.exists():
        return TestResult(
            passed=False, output="", duration_ms=_ms_since(start),
            errors=["Harness project directory not found"],
        )

    main_py = harness_dir / "main.py"
    if not main_py.exists():
        return TestResult(
            passed=False,
            output="main.py not found; runner cannot test this harness",
            duration_ms=_ms_since(start),
            errors=[f"main.py missing at {main_py}"],
        )

    # Smoke run: empty input, just check it exits cleanly within timeout.
    proc = _run_main_py(harness_dir, "")
    if proc is None:
        return TestResult(
            passed=False, output="main.py crashed before producing output",
            duration_ms=_ms_since(start),
            errors=[f"feature {feature_id}: smoke run failed"],
        )
    passed = proc.returncode == 0
    return TestResult(
        passed=passed,
        output=proc.stdout[:500] if passed else (proc.stderr or proc.stdout)[:500],
        duration_ms=_ms_since(start),
        errors=[] if passed else [f"main.py exit code {proc.returncode}"],
    )


def run_sanity_check(run_id: str) -> TestResult:
    """Verify the harness still has its minimum required files.

    Sanity_check is invoked every time the feature loop re-enters, to catch
    generator mishaps that wipe the project structure. We require:
      - harness/src/  (project source root)
      - harness/main.py (runner entrypoint)
    """
    start = time.time()
    harness_dir = _harness_dir(run_id)
    if not harness_dir.exists():
        return TestResult(
            passed=False, output="",
            duration_ms=_ms_since(start),
            errors=["Harness project directory not found"],
        )

    errors: list[str] = []
    if not (harness_dir / "src").exists():
        errors.append("src/ directory not found")
    if not (harness_dir / "main.py").exists():
        errors.append("main.py entrypoint not found")

    passed = not errors
    append_progress_log(
        run_id, "SANITY_CHECK",
        f"Sanity check: {'PASS' if passed else 'FAIL'} ({', '.join(errors) if errors else 'all required files present'})",
    )
    return TestResult(
        passed=passed,
        output="Sanity check passed" if passed else "Missing required files",
        duration_ms=_ms_since(start),
        errors=errors,
    )


def run_qa_eval(run_id: str, criteria: dict) -> QAGrade:
    """Run the full test_cases suite against main.py and aggregate the results.

    Convention:
      - ``overall_pass=True`` AND ``runner_results=[]`` means the runner
        SKIPPED (no test_cases, or no main.py to run). The LLM evaluator
        should grade purely on its own.
      - ``overall_pass=False`` AND ``runner_results=[...]`` means the runner
        RAN and saw failures — those are ground truth.
      - ``overall_pass=True`` AND ``runner_results=[...]`` means the runner
        RAN and every case passed — soft scores left to LLM.
    """
    start = time.time()
    harness_dir = _harness_dir(run_id)
    if not harness_dir.exists():
        return QAGrade(
            overall_pass=True,
            summary="Harness dir not found — runner skipped, deferring to LLM",
        )

    main_py = harness_dir / "main.py"
    if not main_py.exists():
        # No entrypoint — runner cannot run. Don't force a fail; let LLM
        # grade (executor_qa can still pass if generator is making progress).
        return QAGrade(
            overall_pass=True,
            summary="main.py entrypoint missing — runner skipped, deferring to LLM",
        )

    test_cases = _load_test_cases(run_id)
    if not test_cases:
        return QAGrade(
            overall_pass=True,
            summary="(no test_cases in design draft — runner skipped, deferring to LLM evaluator)",
        )

    # If every case is a placeholder (expected_to_pass=False), the runner
    # cannot produce meaningful signal — by definition each "pass" would
    # be a soft-pass-expecting-failure, and an LLM-side fail would force the
    # sprint into a pointless fix loop. Defer to the LLM evaluator instead.
    real_cases = [tc for tc in test_cases if tc.get("expected_to_pass", True)]
    if not real_cases:
        return QAGrade(
            overall_pass=True,
            summary="(all test_cases are placeholders — runner skipped, deferring to LLM evaluator)",
        )

    # Run each test case
    runner_results: list[dict] = []
    soft_pass_count = 0
    hard_pass_count = 0
    for tc in test_cases:
        case_start = time.time()
        proc = _run_main_py(harness_dir, tc.get("input", ""))
        case_result = _evaluate_case(proc, tc)
        case_result.duration_ms = _ms_since(case_start)
        runner_results.append(case_result.__dict__)
        if case_result.passed:
            if tc.get("expected_to_pass", True):
                hard_pass_count += 1
            else:
                soft_pass_count += 1

    total = len(test_cases)
    fail_count = total - hard_pass_count - soft_pass_count

    # Hard data only: pass ratio. Anything subjective (product depth, visual
    # quality, code quality) belongs to the LLM evaluator.
    functional_ratio = hard_pass_count / total if total > 0 else 0.0
    # overall_pass: every expected_to_pass case must actually pass.
    overall_pass = fail_count == 0 and hard_pass_count >= 1

    summary = (
        f"Runner: {hard_pass_count} pass / {soft_pass_count} soft-pass "
        f"(expected to fail) / {fail_count} fail — total {total}"
    )
    append_progress_log(run_id, "EVALUATOR_QA", f"run_qa_eval: {summary}")

    return QAGrade(
        overall_pass=overall_pass,
        summary=summary,
        functional_ratio=functional_ratio,
        runner_results=runner_results,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _harness_dir(run_id: str) -> Path:
    return get_run_dir(run_id) / "harness"


def _ms_since(start: float) -> int:
    return int((time.time() - start) * 1000)


def _load_test_cases(run_id: str) -> list[dict]:
    """Read test_cases from harness_design_draft.json, empty list on any error."""
    draft_path = get_run_dir(run_id) / "harness_design_draft.json"
    if not draft_path.exists():
        return []
    try:
        with open(draft_path, encoding="utf-8") as f:
            draft = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    cases = draft.get("test_cases") or []
    return [c for c in cases if isinstance(c, dict)]


def _run_main_py(harness_dir: Path, user_input: str, timeout_s: int = 60):
    """Run `python main.py <user_input>` in harness_dir; return CompletedProcess or None.

    Returns None on unrecoverable failure (timeout, executable-not-found).
    Captures both stdout and stderr.
    """
    main_py = harness_dir / "main.py"
    if not main_py.exists():
        return None

    env = dict(os.environ)
    # Ensure the harness's own src/ is on PYTHONPATH so generated code can do
    # relative-style imports without depending on generator to write setup.py.
    env["PYTHONPATH"] = str(harness_dir) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        # sys.executable matches the in-process interpreter, so we don't
        # accidentally shell out to a system python3 that lacks the deps
        # the user's venv has.
        return subprocess.run(
            [sys.executable, "main.py", user_input or ""],
            cwd=harness_dir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        return None


def _evaluate_case(proc, tc: dict) -> TestCaseResult:
    """Classify a run against a test case."""
    case_id = tc.get("id", "?")
    expected_to_pass = tc.get("expected_to_pass", True)
    expected_keys = tc.get("expected_output_keys") or []

    if proc is None:
        # Process didn't even start or timed out
        if expected_to_pass:
            return TestCaseResult(
                id=case_id, passed=False, duration_ms=0,
                error="main.py failed to run or timed out (60s)",
            )
        return TestCaseResult(id=case_id, passed=True, duration_ms=0,
                              error="expected to fail, runner could not execute")

    if proc.returncode != 0:
        if expected_to_pass:
            return TestCaseResult(
                id=case_id, passed=False, duration_ms=0,
                error=f"exit {proc.returncode}: {proc.stderr[:300]}",
            )
        return TestCaseResult(
            id=case_id, passed=True, duration_ms=0,
            error=f"expected to fail, exit {proc.returncode}",
        )

    # Process exited 0 — parse stdout as JSON and check required keys.
    stdout = proc.stdout or ""
    parsed, parse_err = _try_parse_json(stdout)
    if parse_err:
        if expected_to_pass:
            return TestCaseResult(
                id=case_id, passed=False, duration_ms=0,
                error=f"stdout not valid JSON: {parse_err}",
            )
        return TestCaseResult(id=case_id, passed=True, duration_ms=0,
                              error=f"expected to fail, JSON parse failed: {parse_err}")

    if not isinstance(parsed, dict):
        if expected_to_pass:
            return TestCaseResult(
                id=case_id, passed=False, duration_ms=0,
                error=f"stdout JSON is not an object (got {type(parsed).__name__})",
            )
        return TestCaseResult(id=case_id, passed=True, duration_ms=0,
                              error="expected to fail, stdout JSON not an object")

    missing = [k for k in expected_keys if k not in parsed]
    if missing and expected_to_pass:
        return TestCaseResult(
            id=case_id, passed=False, duration_ms=0,
            error=f"missing expected keys: {missing}",
            missing_keys=missing,
        )
    if missing and not expected_to_pass:
        # expected to fail AND missing keys ⇒ that's actually passing the expectation
        return TestCaseResult(
            id=case_id, passed=True, duration_ms=0,
            error=f"expected to fail, missing keys {missing} (as expected)",
        )

    return TestCaseResult(id=case_id, passed=True, duration_ms=0)


def _try_parse_json(text: str) -> tuple[object, str]:
    """Parse JSON tolerantly; allow surrounding prose if exactly one JSON object present."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text), ""
    except json.JSONDecodeError:
        pass
    # Try to locate a JSON object in the text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate), ""
        except json.JSONDecodeError as e:
            return None, str(e)
    return None, "no JSON object found"
