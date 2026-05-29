"""CTest command for structured test exports."""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.context import get_exports_dir, get_project_root
from ..core.dry_run import is_dry_run
from ..core.utils import write_json


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the test command."""
    parser = subparsers.add_parser(
        "test",
        help="Run CTest suites and emit structured results",
    )
    parser.add_argument("--build-dir", default="build", help="CMake build directory")
    parser.add_argument("--regex", help="Only run tests matching this regular expression")
    parser.add_argument("--exclude", help="Exclude tests matching this regular expression")
    parser.add_argument("--label", help="Only run tests with labels matching this regex")
    parser.add_argument("--parallel", "-j", type=int, help="Number of parallel test jobs")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds for each test")
    parser.add_argument("--rerun-failed", action="store_true", help="Re-run tests that previously failed")
    parser.add_argument("--preview", action="store_true", help="List tests without executing them")
    parser.add_argument("--json", nargs="?", const="", help="Optional JSON summary path")
    parser.add_argument("--sarif", nargs="?", const="", help="Optional SARIF report path")
    parser.set_defaults(func=handle_test)


def handle_test(args: argparse.Namespace) -> int:
    """Handle the test command."""
    exports_dir = get_exports_dir() / "tests"
    json_path = Path(args.json) if args.json else exports_dir / "ctest_results.json"
    sarif_path = Path(args.sarif) if args.sarif else exports_dir / "ctest_results.sarif"
    junit_path = exports_dir / "Test.xml"
    stdout_path = exports_dir / "ctest_stdout.txt"
    stderr_path = exports_dir / "ctest_stderr.txt"

    cmd = build_ctest_command(args, junit_path)
    if is_dry_run():
        print("[DRY RUN] Would run CTest:")
        print("  " + " ".join(cmd))
        return 0

    exports_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    if shutil.which("ctest") is None:
        summary = build_missing_ctest_summary(cmd, args.build_dir, time.monotonic() - start)
        write_json(json_path, summary)
        write_sarif(sarif_path, summary)
        print(str(json_path))
        return 127

    result = subprocess.run(
        cmd,
        cwd=get_project_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    duration = time.monotonic() - start
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    summary = build_ctest_summary(
        cmd=cmd,
        build_dir=args.build_dir,
        return_code=result.returncode,
        duration_seconds=duration,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        junit_path=junit_path if junit_path.exists() else None,
        preview=args.preview,
    )
    write_json(json_path, summary)
    write_sarif(sarif_path, summary)
    print(str(json_path))
    return result.returncode


def build_ctest_command(args: argparse.Namespace, junit_path: Path) -> List[str]:
    """Build the CTest invocation."""
    cmd = ["ctest", "--test-dir", str(args.build_dir)]
    if args.preview:
        cmd.append("-N")
    else:
        cmd.extend(["--output-on-failure", "--no-tests=error"])
        cmd.extend(["--output-junit", str(junit_path)])
    if args.regex:
        cmd.extend(["-R", args.regex])
    if args.exclude:
        cmd.extend(["-E", args.exclude])
    if args.label:
        cmd.extend(["-L", args.label])
    if args.parallel:
        cmd.extend(["-j", str(args.parallel)])
    if args.timeout:
        cmd.extend(["--timeout", str(args.timeout)])
    if args.rerun_failed:
        cmd.append("--rerun-failed")
    return cmd


def build_missing_ctest_summary(cmd: List[str], build_dir: str, duration_seconds: float) -> Dict[str, Any]:
    """Build a structured failure when ctest is unavailable."""
    return {
        "_meta": base_meta(cmd, build_dir, 127, duration_seconds, "", "ctest not found on PATH", None),
        "stats": empty_stats(duration_seconds),
        "failures": [{"name": "ctest", "status": "error", "fail_reason": "ctest not found on PATH"}],
        "tests": [],
    }


def build_ctest_summary(
    *,
    cmd: List[str],
    build_dir: str,
    return_code: int,
    duration_seconds: float,
    stdout: str,
    stderr: str,
    junit_path: Optional[Path],
    preview: bool,
) -> Dict[str, Any]:
    """Build the JSON summary for a CTest run."""
    tests = parse_junit(junit_path) if junit_path and not preview else parse_ctest_preview(stdout)
    stats = summarize_tests(tests, duration_seconds)
    failures = [
        {
            "name": test["name"],
            "status": test["status"],
            "fail_reason": test.get("fail_reason"),
        }
        for test in tests
        if test["status"] in {"failed", "timeout", "error"}
    ]
    if return_code != 0 and not failures:
        failures.append({"name": "ctest", "status": "error", "fail_reason": "CTest returned non-zero"})

    return {
        "_meta": base_meta(cmd, build_dir, return_code, duration_seconds, stdout, stderr, junit_path),
        "stats": stats,
        "failures": failures,
        "tests": tests,
    }


def base_meta(
    cmd: List[str],
    build_dir: str,
    return_code: int,
    duration_seconds: float,
    stdout: str,
    stderr: str,
    junit_path: Optional[Path],
) -> Dict[str, Any]:
    """Build shared summary metadata."""
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ctest_command": " ".join(cmd),
        "build_dir": build_dir,
        "ctest_version": ctest_version(),
        "return_code": return_code,
        "duration_seconds": round(duration_seconds, 3),
        "stdout": limit_text(stdout),
        "stderr": limit_text(stderr),
        "xml": str(junit_path) if junit_path else None,
    }


def ctest_version() -> Optional[str]:
    """Return the ctest version line if available."""
    if shutil.which("ctest") is None:
        return None
    result = subprocess.run(["ctest", "--version"], capture_output=True, text=True, check=False)
    return (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else None


def parse_junit(path: Optional[Path]) -> List[Dict[str, Any]]:
    """Parse CTest JUnit output."""
    if not path or not path.exists():
        return []
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except ET.ParseError:
        return []

    testcases = root.findall(".//testcase")
    tests: List[Dict[str, Any]] = []
    for case in testcases:
        name = case.attrib.get("name") or case.attrib.get("classname") or "unknown"
        duration = _float_or_none(case.attrib.get("time"))
        labels = []
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if failure is not None:
            status = "failed"
            reason = failure.attrib.get("message") or (failure.text or "").strip() or None
        elif error is not None:
            status = "error"
            reason = error.attrib.get("message") or (error.text or "").strip() or None
        elif skipped is not None:
            status = "skipped"
            reason = skipped.attrib.get("message") or (skipped.text or "").strip() or None
        else:
            status = "passed"
            reason = None
        tests.append(
            {
                "name": name,
                "status": status,
                "duration": duration,
                "labels": labels,
                "fail_reason": limit_text(reason, 500) if reason else None,
            }
        )
    return tests


def parse_ctest_preview(stdout: str) -> List[Dict[str, Any]]:
    """Parse ctest -N output into test entries."""
    tests: List[Dict[str, Any]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("Test #"):
            continue
        _, _, tail = stripped.partition(":")
        name = tail.strip() if tail else stripped
        tests.append({"name": name, "status": "notrun", "duration": None, "labels": [], "fail_reason": None})
    return tests


def summarize_tests(tests: List[Dict[str, Any]], duration_seconds: float) -> Dict[str, Any]:
    """Summarize parsed tests."""
    stats = empty_stats(duration_seconds)
    stats["total"] = len(tests)
    for test in tests:
        status = test["status"]
        if status in stats:
            stats[status] += 1
        elif status == "failed":
            stats["failed"] += 1
        elif status == "error":
            stats["failed"] += 1
        else:
            stats["unknown"] += 1
    return stats


def empty_stats(duration_seconds: float) -> Dict[str, Any]:
    """Return a zeroed stats object."""
    return {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "timeout": 0,
        "notrun": 0,
        "skipped": 0,
        "unknown": 0,
        "duration_seconds": round(duration_seconds, 3),
    }


def write_sarif(path: Path, summary: Dict[str, Any]) -> None:
    """Write a small SARIF report for failed tests."""
    results = []
    for failure in summary.get("failures", []):
        results.append(
            {
                "ruleId": "ctest.failure",
                "level": "error",
                "message": {"text": f"{failure['name']}: {failure.get('fail_reason') or failure['status']}"},
            }
        )
    sarif = {
        "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "llmtk-test",
                        "informationUri": "https://github.com/gregvw/llm-cpp-toolkit",
                        "rules": [
                            {
                                "id": "ctest.failure",
                                "name": "CTest Failure",
                                "shortDescription": {"text": "CTest reported a failing test"},
                            }
                        ],
                    }
                },
                "results": results,
            }
        ],
    }
    write_json(path, sarif)


def _float_or_none(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def limit_text(text: Optional[str], max_chars: int = 16000) -> str:
    """Bound captured text in JSON summaries."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[truncated]"


def run_test_for_agent(params: dict) -> int:
    """Run tests from structured agent/MCP parameters."""
    args = argparse.Namespace(
        build_dir=params.get("build_dir", "build"),
        regex=params.get("regex"),
        exclude=params.get("exclude"),
        label=params.get("label"),
        parallel=params.get("parallel"),
        timeout=params.get("timeout"),
        rerun_failed=bool(params.get("rerun_failed", False)),
        preview=bool(params.get("preview", False)),
        json=params.get("json", ""),
        sarif=params.get("sarif", ""),
    )
    return handle_test(args)
