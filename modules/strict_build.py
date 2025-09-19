"""Strict build orchestration helpers for llmtk.

Provides utilities to configure, build, and test CMake projects with
opinionated warning flags, sanitizers, and clang-tidy integration. Designed to
produce filtered, LLM-friendly output while preserving detailed logs on disk.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

STRICT_WARNING_FLAGS = ["-Wall", "-Wextra", "-Wconversion", "-Wshadow", "-Werror"]
SANITIZER_FLAGS = ["-fsanitize=address", "-fsanitize=undefined"]
DEFAULT_STD = "23"
DEFAULT_BUILD_TYPE = "Debug"
DEFAULT_GENERATOR = "Ninja"
DEFAULT_TIDY_CHECKS = (
    "cppcoreguidelines-*,-cppcoreguidelines-avoid-non-const-global-variables,"
    "bugprone-*,performance-*,modernize-*,readability-*,clang-analyzer-*"
)
IMPORTANT_LINE_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"error", r"warning", r"FAILED", r"(?:100|[1-9]?\d)% tests",
        r"The following tests FAILED", r"ninja:\s*(?:error|warning)",
        r"^-- (?:Configuring|Generating|Build|Installing)",
    ]
]


@dataclass
class StageResult:
    """Result of running a configure/build/test stage."""

    name: str
    command: List[str]
    returncode: int
    duration_seconds: float
    log_path: pathlib.Path
    filtered_lines: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 4),
            "log": str(self.log_path),
            "highlights": self.filtered_lines,
        }


def _now_stamp() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: pathlib.Path) -> pathlib.Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _filter_lines(stream: Iterable[str]) -> List[str]:
    highlights: List[str] = []
    for line in stream:
        text = line.rstrip()
        if not text:
            continue
        if any(pat.search(text) for pat in IMPORTANT_LINE_PATTERNS):
            highlights.append(text)
    return highlights


def _normalize_path(path: pathlib.Path | str) -> pathlib.Path:
    return pathlib.Path(path).resolve()


def _quote_list(items: Sequence[str]) -> List[str]:
    return [str(item) for item in items]


def strict_configure_command(
    source_dir: pathlib.Path | str,
    build_dir: pathlib.Path | str,
    *,
    std: str = DEFAULT_STD,
    build_type: str = DEFAULT_BUILD_TYPE,
    generator: str = DEFAULT_GENERATOR,
    extra_defines: Optional[Sequence[str]] = None,
    extra_args: Optional[Sequence[str]] = None,
    use_ccache: bool = True,
    enable_tidy: bool = True,
    tidy_checks: str = DEFAULT_TIDY_CHECKS,
) -> List[str]:
    """Return a cmake configure command with strict defaults."""

    source_dir = _normalize_path(source_dir)
    build_dir = _normalize_path(build_dir)

    cmd: List[str] = [
        "cmake",
        "-S",
        str(source_dir),
        "-B",
        str(build_dir),
        "-G",
        generator,
        f"-DCMAKE_BUILD_TYPE={build_type}",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        f"-DCMAKE_CXX_STANDARD={std}",
        "-DCMAKE_CXX_STANDARD_REQUIRED=ON",
        "-DCMAKE_CXX_EXTENSIONS=OFF",
    ]

    joined_warnings = " ".join(STRICT_WARNING_FLAGS)
    joined_sanitizers = " ".join(SANITIZER_FLAGS)
    combined_flags = f"{joined_warnings} {joined_sanitizers}".strip()

    cmd.append(f"-DCMAKE_CXX_FLAGS={combined_flags}")
    cmd.append(f"-DCMAKE_C_FLAGS={combined_flags}")
    cmd.append(f"-DCMAKE_EXE_LINKER_FLAGS={joined_sanitizers}")
    cmd.append(f"-DCMAKE_SHARED_LINKER_FLAGS={joined_sanitizers}")

    if use_ccache and shutil.which("ccache"):
        cmd.append("-DCMAKE_CXX_COMPILER_LAUNCHER=ccache")
        cmd.append("-DCMAKE_C_COMPILER_LAUNCHER=ccache")

    if enable_tidy:
        tidy = shutil.which("clang-tidy") or "clang-tidy"
        tidy_value = f"{tidy};-checks={tidy_checks};-warnings-as-errors=*"
        cmd.append(f"-DCMAKE_CXX_CLANG_TIDY={tidy_value}")

    if extra_defines:
        for define in extra_defines:
            if not define:
                continue
            if not define.startswith("-D"):
                cmd.append(f"-D{define}")
            else:
                cmd.append(define)

    if extra_args:
        cmd.extend(_quote_list(extra_args))

    return cmd


def strict_build_command(
    build_dir: pathlib.Path | str,
    *,
    target: Optional[str] = None,
    jobs: Optional[int] = None,
    build_tool_args: Optional[Sequence[str]] = None,
) -> List[str]:
    """Return a cmake --build command aligned with strict configuration."""

    build_dir = _normalize_path(build_dir)
    cmd: List[str] = ["cmake", "--build", str(build_dir)]
    if target:
        cmd.extend(["--target", target])
    if jobs and jobs > 0:
        cmd.extend(["--parallel", str(jobs)])
    if build_tool_args:
        cmd.append("--")
        cmd.extend(_quote_list(build_tool_args))
    return cmd


def strict_test_command(
    build_dir: pathlib.Path | str,
    *,
    label: Optional[str] = None,
    regex: Optional[str] = None,
    jobs: Optional[int] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> List[str]:
    """Return a ctest command with structured friendly defaults."""

    build_dir = _normalize_path(build_dir)
    cmd: List[str] = [
        "ctest",
        "--test-dir",
        str(build_dir),
        "--output-on-failure",
        "--no-tests=error",
    ]
    if label:
        cmd.extend(["-L", label])
    if regex:
        cmd.extend(["-R", regex])
    if jobs and jobs > 0:
        cmd.extend(["-j", str(jobs)])
    if extra_args:
        cmd.extend(_quote_list(extra_args))
    return cmd


class StrictBuildManager:
    """High-level orchestrator providing strict build flows."""

    def __init__(
        self,
        source_dir: pathlib.Path | str = pathlib.Path.cwd(),
        build_dir: pathlib.Path | str = "build",
        log_dir: pathlib.Path | str = pathlib.Path("logs") / "strict_build",
    ) -> None:
        self.source_dir = _normalize_path(source_dir)
        self.build_dir = _normalize_path(build_dir)
        self.log_dir = _ensure_dir(_normalize_path(log_dir))

    def _run(self, command: List[str], stage: str) -> StageResult:
        log_path = self.log_dir / f"{stage}_{_now_stamp()}.log"
        highlights: List[str] = []
        start = time.perf_counter()
        with open(log_path, "w", encoding="utf-8", errors="replace") as log:
            proc = subprocess.Popen(
                command,
                cwd=self.source_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                if any(pat.search(line) for pat in IMPORTANT_LINE_PATTERNS):
                    highlights.append(line.rstrip())
                    sys.stdout.write(line)
                    sys.stdout.flush()
            proc.wait()
            returncode = proc.returncode or 0
        duration = time.perf_counter() - start
        if returncode != 0:
            print(f"❌ {stage} failed (logs: {log_path})")
        else:
            print(f"✅ {stage} completed in {duration:.2f}s (logs: {log_path})")
        return StageResult(stage, command, returncode, duration, log_path, highlights)

    def configure(self, **kwargs) -> StageResult:
        command = strict_configure_command(self.source_dir, self.build_dir, **kwargs)
        return self._run(command, "configure")

    def build(self, **kwargs) -> StageResult:
        command = strict_build_command(self.build_dir, **kwargs)
        return self._run(command, "build")

    def test(self, **kwargs) -> StageResult:
        command = strict_test_command(self.build_dir, **kwargs)
        return self._run(command, "test")

    def full(self, run_tests: bool = True, **kwargs) -> List[StageResult]:
        """Run configure -> build -> optional test and return stage results."""

        configure_kwargs = kwargs.get("configure", {})
        build_kwargs = kwargs.get("build", {})
        test_kwargs = kwargs.get("test", {})

        results = [self.configure(**configure_kwargs)]
        if results[-1].returncode != 0:
            return results

        results.append(self.build(**build_kwargs))
        if results[-1].returncode != 0 or not run_tests:
            return results

        results.append(self.test(**test_kwargs))
        return results


def _write_summary(path: pathlib.Path, stages: Sequence[StageResult]) -> None:
    data = {
        "generated_at": _dt.datetime.now(_dt.UTC).isoformat(),
        "stages": [stage.summary() for stage in stages],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strict CMake build helper with sanitizer + clang-tidy defaults",
    )
    parser.add_argument("--source", default=".", help="Source directory")
    parser.add_argument("--build", default="build", help="Build directory")
    parser.add_argument("--logs", default=str(pathlib.Path("logs") / "strict_build"), help="Log directory")

    sub = parser.add_subparsers(dest="cmd", required=True)

    cfg = sub.add_parser("configure", help="Run cmake configure with strict flags")
    cfg.add_argument("--std", default=DEFAULT_STD)
    cfg.add_argument("--build-type", default=DEFAULT_BUILD_TYPE)
    cfg.add_argument("--generator", default=DEFAULT_GENERATOR)
    cfg.add_argument("--no-ccache", action="store_true")
    cfg.add_argument("--no-tidy", action="store_true")
    cfg.add_argument("--tidy-checks", default=DEFAULT_TIDY_CHECKS)
    cfg.add_argument("extra", nargs="*", help="Additional -D style arguments")

    bld = sub.add_parser("build", help="Build targets with strict defaults")
    bld.add_argument("--target")
    bld.add_argument("--jobs", type=int)
    bld.add_argument("--tool-arg", action="append", dest="tool_args")

    tst = sub.add_parser("test", help="Run ctest with filtered output")
    tst.add_argument("--label")
    tst.add_argument("--regex")
    tst.add_argument("--jobs", type=int)
    tst.add_argument("extra", nargs="*")

    full = sub.add_parser("full", help="Configure + build + test")
    full.add_argument("--skip-tests", action="store_true")
    full.add_argument("--std", default=DEFAULT_STD)
    full.add_argument("--build-type", default=DEFAULT_BUILD_TYPE)
    full.add_argument("--generator", default=DEFAULT_GENERATOR)
    full.add_argument("--no-ccache", action="store_true")
    full.add_argument("--no-tidy", action="store_true")
    full.add_argument("--tidy-checks", default=DEFAULT_TIDY_CHECKS)
    full.add_argument("--target")
    full.add_argument("--jobs", type=int)
    full.add_argument("--tool-arg", action="append", dest="tool_args")
    full.add_argument("--test-label")
    full.add_argument("--test-regex")
    full.add_argument("--test-jobs", type=int)

    args = parser.parse_args(argv)

    manager = StrictBuildManager(args.source, args.build, args.logs)

    if args.cmd == "configure":
        result = manager.configure(
            std=args.std,
            build_type=args.build_type,
            generator=args.generator,
            use_ccache=not args.no_ccache,
            enable_tidy=not args.no_tidy,
            tidy_checks=args.tidy_checks,
            extra_defines=args.extra,
        )
        _write_summary(manager.log_dir / "configure_latest.json", [result])
        return result.returncode

    if args.cmd == "build":
        result = manager.build(target=args.target, jobs=args.jobs, build_tool_args=args.tool_args)
        _write_summary(manager.log_dir / "build_latest.json", [result])
        return result.returncode

    if args.cmd == "test":
        result = manager.test(label=args.label, regex=args.regex, jobs=args.jobs, extra_args=args.extra)
        _write_summary(manager.log_dir / "test_latest.json", [result])
        return result.returncode

    if args.cmd == "full":
        configure_kwargs = {
            "std": args.std,
            "build_type": args.build_type,
            "generator": args.generator,
            "use_ccache": not args.no_ccache,
            "enable_tidy": not args.no_tidy,
            "tidy_checks": args.tidy_checks,
        }
        build_kwargs = {
            "target": args.target,
            "jobs": args.jobs,
            "build_tool_args": args.tool_args,
        }
        test_kwargs = {
            "label": args.test_label,
            "regex": args.test_regex,
            "jobs": args.test_jobs,
        }
        results = manager.full(
            run_tests=not args.skip_tests,
            configure=configure_kwargs,
            build=build_kwargs,
            test=test_kwargs,
        )
        _write_summary(manager.log_dir / "full_latest.json", results)
        worst_rc = max((stage.returncode for stage in results), default=0)
        return worst_rc

    return 0


if __name__ == "__main__":
    sys.exit(main())
