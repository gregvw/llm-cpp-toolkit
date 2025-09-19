#!/usr/bin/env python3
"""Wrapper used by `llmtk bench` to execute commands with extra metrics.

This script records execution duration, peak RSS, and filtered highlights while
preserving full logs for later inspection.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import re
import resource
import shlex
import subprocess
import sys
import time
from typing import Iterable, List

IMPORTANT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"error",
        r"warning",
        r"FAILED",
        r"ninja:\s*(?:error|warning)",
        r"The following tests FAILED",
        r"100% tests passed",
    ]
]


def _filter_lines(stream: Iterable[str]) -> List[str]:
    highlights: List[str] = []
    for line in stream:
        text = line.rstrip()
        if not text:
            continue
        if any(pat.search(text) for pat in IMPORTANT_PATTERNS):
            highlights.append(text)
    return highlights


def _normalize_rss_kib(raw: float) -> float:
    # Linux reports kilobytes, macOS reports bytes.
    if platform.system() == "Darwin":
        return raw / 1024.0
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="llmtk bench execution wrapper")
    parser.add_argument("--metrics", required=True, help="Path to append JSON metrics (one per line)")
    parser.add_argument("--stage", required=True, help="Stage name (configure/build/test)")
    parser.add_argument("--log", required=True, help="Path to store complete combined stdout/stderr log")
    parser.add_argument("--keep-output", action="store_true", help="Also stream all command output to stdout")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute (prefix with --)")
    args = parser.parse_args()

    if not args.cmd or args.cmd[0] != "--":
        parser.error("Command must be specified after --")
    command = args.cmd[1:]

    log_path = pathlib.Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    highlights: List[str] = []

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    with open(log_path, "w", encoding="utf-8", errors="replace") as log_file:
        for line in process.stdout:
            log_file.write(line)
            if args.keep_output:
                sys.stdout.write(line)
            else:
                if any(pat.search(line) for pat in IMPORTANT_PATTERNS):
                    highlights.append(line.rstrip())
                    sys.stdout.write(line)
            sys.stdout.flush()

    returncode = process.wait()
    duration = time.perf_counter() - start

    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    peak_rss_kib = _normalize_rss_kib(float(usage.ru_maxrss))

    metrics = {
        "stage": args.stage,
        "command": command,
        "returncode": returncode,
        "duration_seconds": duration,
        "peak_rss_kib": peak_rss_kib,
        "log": str(log_path),
        "highlights": highlights,
        "timestamp": time.time(),
    }

    metrics_path = pathlib.Path(args.metrics)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(metrics) + "\n")

    return returncode


if __name__ == "__main__":
    sys.exit(main())
