#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(pwd)
EXPORTS_DIR="$ROOT_DIR/exports/reports"
mkdir -p "$EXPORTS_DIR"

# Add local tools to PATH if they exist
LOCAL_BIN="$ROOT_DIR/.llmtk/bin"
if [[ -d "$LOCAL_BIN" ]]; then
    export PATH="$LOCAL_BIN:$PATH"
fi

COMPILE_DB="$ROOT_DIR/exports/compile_commands.json"
if [[ ! -f "$COMPILE_DB" && -f "$ROOT_DIR/compile_commands.json" ]]; then
  COMPILE_DB="$ROOT_DIR/compile_commands.json"
fi

if [[ $# -gt 0 ]]; then
  PATH_FILTERS=("$@")
else
  PATH_FILTERS=("src" "include" ".")
fi

export LLMTK_PROJECT_ROOT="$ROOT_DIR"

COMPILE_DB_ARG="$COMPILE_DB"
if [[ ! -f "$COMPILE_DB_ARG" ]]; then
  COMPILE_DB_ARG="__NONE__"
fi

python3 - "$EXPORTS_DIR" "$COMPILE_DB_ARG" "${PATH_FILTERS[@]}" <<'PY'
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
DIAG_RE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+):(?P<column>\d+):\s+"
    r"(?P<severity>warning|error|note|fatal error|remark):\s+"
    r"(?P<message>.*?)(?:\s+\[(?P<check>[^\]]+)\])?$"
)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def relativize(path_str: str, root: Path) -> str:
    try:
        path = Path(path_str)
        if not path.is_absolute():
            path = (root / path).resolve()
        else:
            path = path.resolve()
        return str(path.relative_to(root))
    except Exception:
        return path_str


def collect_translation_units(compile_db: Optional[Path], filters: List[str], root: Path) -> List[Path]:
    if not compile_db or not compile_db.exists():
        return []
    try:
        data = json.loads(compile_db.read_text())
    except json.JSONDecodeError:
        return []

    resolved_filters: List[str] = []
    for raw in filters:
        if not raw:
            continue
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = (root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        resolved_filters.append(str(candidate))

    def matches(path: Path) -> bool:
        if not resolved_filters:
            return True
        target = str(path)
        for item in resolved_filters:
            if target == item or target.startswith(item + os.sep):
                return True
        return False

    seen: set[str] = set()
    tus: List[Path] = []
    source_suffixes = {".c", ".cc", ".cpp", ".cxx", ".c++", ".m", ".mm", ".ixx", ".cppm"}

    for entry in data:
        file_path = Path(entry.get("file", ""))
        directory = Path(entry.get("directory", "."))
        if not file_path.is_absolute():
            file_path = (directory / file_path).resolve()
        else:
            file_path = file_path.resolve()

        if file_path.suffix.lower() not in source_suffixes:
            continue
        key = str(file_path)
        if key in seen:
            continue
        if not matches(file_path):
            continue
        seen.add(key)
        tus.append(file_path)

    return tus


def parse_clang_tidy_output(output: str, root: Path) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    diagnostics: List[Dict[str, Any]] = []
    counts = {"warning": 0, "error": 0, "note": 0}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        match = DIAG_RE.match(line)
        if not match:
            continue
        file_token = match.group("file")
        diag = {
            "file": relativize(file_token, root),
            "line": int(match.group("line")),
            "column": int(match.group("column")),
            "severity": match.group("severity"),
            "message": match.group("message"),
        }
        check = match.group("check")
        if check:
            diag["check"] = check
        counts[diag["severity"]] = counts.get(diag["severity"], 0) + 1
        diagnostics.append(diag)
    return diagnostics, counts


def limited_text(text: str, max_chars: int = 16000, max_lines: int = 200) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append("[truncated]")
        text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[truncated]"
    return text


def run_clang_tidy(tus: List[Path], compile_db: Optional[Path], exports_dir: Path, root: Path) -> Dict[str, Any]:
    binary = shutil.which("clang-tidy")
    if not binary:
        return {
            "tool": "clang-tidy",
            "ok": False,
            "status": "missing_binary",
            "message": "clang-tidy not found on PATH",
        }

    if not compile_db or not compile_db.exists():
        return {
            "tool": "clang-tidy",
            "ok": False,
            "status": "missing_compile_commands",
            "message": "compile_commands.json not found. Run llmtk context export or compile_db first.",
        }

    if not tus:
        return {
            "tool": "clang-tidy",
            "ok": True,
            "status": "no_translation_units",
            "diagnostics": [],
            "diagnostic_counts": {"warning": 0, "error": 0, "note": 0, "fatal error": 0, "remark": 0},
            "files_processed": 0,
        }

    env = os.environ.copy()
    env.setdefault("CLANG_FORCE_COLOR_DIAGNOSTICS", "0")

    run_clang_tidy_binary = shutil.which("run-clang-tidy")
    compile_db_dir = compile_db.parent
    fix_path = exports_dir / "clang-tidy-fixes.yaml"
    if fix_path.exists():
        fix_path.unlink()

    checks = env.get("LLMTK_CLANG_TIDY_CHECKS")

    command: list[str]
    stdout_text = ""
    stderr_text = ""
    exit_code = 0
    start = time.monotonic()

    files = [str(path) for path in tus]
    job_count = min(len(files), max(os.cpu_count() or 1, 1))

    if run_clang_tidy_binary:
        command = [run_clang_tidy_binary, "-quiet", "-p", str(compile_db_dir), "-j", str(job_count)]
        if checks:
            command.append(f"-checks={checks}")
        command.append(f"-export-fixes={fix_path}")
        command.extend(files)
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=root,
            env=env,
        )
        stdout_text = strip_ansi(proc.stdout)
        stderr_text = strip_ansi(proc.stderr)
        exit_code = proc.returncode
    else:
        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []
        exit_code = 0
        command = []
        for file_path in files:
            cmd = [binary, "-p", str(compile_db_dir), "-quiet", file_path]
            if checks:
                cmd.append(f"-checks={checks}")
            command.append(" ".join(shlex.quote(part) for part in cmd))
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
            )
            stdout_chunks.append(strip_ansi(proc.stdout))
            stderr_chunks.append(strip_ansi(proc.stderr))
            exit_code = proc.returncode if proc.returncode != 0 else exit_code
        stdout_text = "\n".join(stdout_chunks)
        stderr_text = "\n".join(stderr_chunks)

    duration = time.monotonic() - start

    diagnostics, counts = parse_clang_tidy_output(stdout_text + "\n" + stderr_text, root)
    result = {
        "tool": "clang-tidy",
        "ok": exit_code == 0,
        "status": "completed" if exit_code == 0 else "completed_with_issues",
        "exit_code": exit_code,
        "command": command,
        "files_processed": len(files),
        "diagnostics": diagnostics,
        "diagnostic_counts": counts,
        "duration_seconds": round(duration, 3),
        "stdout": limited_text(stdout_text),
        "stderr": limited_text(stderr_text),
    }
    if fix_path.exists():
        result["export_fixes"] = str(fix_path.relative_to(root)) if fix_path.is_file() else str(fix_path)
    return result


def parse_iwyu_output(output: str, root: Path) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    issues: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    section: Optional[str] = None
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped and section != "full":
            continue
        if stripped.endswith("should add these lines:"):
            if current:
                issues.append(current)
            file_token = stripped[: -len(" should add these lines:")]
            current = {
                "file": relativize(file_token, root),
                "suggest_add": [],
                "suggest_remove": [],
                "full_include_list": [],
            }
            section = "add"
            continue
        if stripped == "should remove these lines:" and current is not None:
            section = "remove"
            continue
        if stripped.startswith("The full include-list for "):
            file_token = stripped[len("The full include-list for ") :].rstrip(":")
            if current and current["file"] != relativize(file_token, root):
                issues.append(current)
                current = {
                    "file": relativize(file_token, root),
                    "suggest_add": [],
                    "suggest_remove": [],
                    "full_include_list": [],
                }
            elif current is None:
                current = {
                    "file": relativize(file_token, root),
                    "suggest_add": [],
                    "suggest_remove": [],
                    "full_include_list": [],
                }
            section = "full"
            continue
        if stripped.startswith("---"):
            if current:
                issues.append(current)
                current = None
            section = None
            continue
        if current is not None and section:
            if section == "add":
                if stripped:
                    current["suggest_add"].append(stripped)
            elif section == "remove":
                if stripped:
                    current["suggest_remove"].append(stripped.lstrip("- "))
            elif section == "full":
                current["full_include_list"].append(stripped)

    if current:
        issues.append(current)

    summary = {
        "files_with_suggestions": len(issues),
        "total_additions": sum(len(item["suggest_add"]) for item in issues),
        "total_removals": sum(len(item["suggest_remove"]) for item in issues),
    }
    return issues, summary


def run_iwyu(tus: List[Path], compile_db: Optional[Path], root: Path) -> Dict[str, Any]:
    iwyu_runner = None
    for candidate in ("iwyu_tool", "iwyu_tool.py"):
        found = shutil.which(candidate)
        if found:
            iwyu_runner = found
            break

    if not iwyu_runner:
        return {
            "tool": "include-what-you-use",
            "ok": False,
            "status": "missing_runner",
            "message": "iwyu_tool (or iwyu_tool.py) not found on PATH",
        }

    if not compile_db or not compile_db.exists():
        return {
            "tool": "include-what-you-use",
            "ok": False,
            "status": "missing_compile_commands",
            "message": "compile_commands.json not found. Run llmtk context export or compile_db first.",
        }

    if not tus:
        return {
            "tool": "include-what-you-use",
            "ok": True,
            "status": "no_translation_units",
            "issues": [],
            "summary": {"files_with_suggestions": 0, "total_additions": 0, "total_removals": 0},
        }

    env = os.environ.copy()
    env.setdefault("IWYU_FORCE_COLOR", "0")

    compile_db_dir = compile_db.parent
    files = [str(path) for path in tus]
    command: list[str]
    if iwyu_runner.endswith(".py"):
        python_executable = sys.executable if sys.executable else "python3"
        command = [python_executable, iwyu_runner, "-p", str(compile_db_dir)]
    else:
        command = [iwyu_runner, "-p", str(compile_db_dir)]
    command.append("-j")
    command.append(str(min(len(files), max(os.cpu_count() or 1, 1))))
    command.extend(files)

    start = time.monotonic()
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    duration = time.monotonic() - start

    stdout_text = strip_ansi(proc.stdout)
    stderr_text = strip_ansi(proc.stderr)

    issues, summary = parse_iwyu_output(stdout_text, root)
    ok = proc.returncode == 0
    status = "completed" if ok else "completed_with_issues"
    result = {
        "tool": "include-what-you-use",
        "ok": ok,
        "status": status,
        "exit_code": proc.returncode,
        "command": command,
        "issues": issues,
        "summary": summary,
        "duration_seconds": round(duration, 3),
        "stdout": limited_text(stdout_text),
        "stderr": limited_text(stderr_text),
    }
    return result


def parse_cppcheck_xml(xml_text: str, root: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, int]]]:
    errors: List[Dict[str, Any]] = []
    if not xml_text.strip():
        return errors, {"by_severity": {}}

    try:
        tree = ET.fromstring(xml_text)
    except ET.ParseError:
        return errors, {"by_severity": {}}

    severity_counts: dict[str, int] = {}
    for error in tree.findall('.//error'):
        severity = error.get('severity', 'unknown')
        message = error.get('msg', '')
        error_id = error.get('id', '')
        verbose = error.get('verbose')
        locations: List[Dict[str, Any]] = []
        for loc in error.findall('location'):
            file_token = loc.get('file', '')
            line = loc.get('line')
            column = loc.get('column')
            locations.append({
                'file': relativize(file_token, root),
                'line': int(line) if line else None,
                'column': int(column) if column else None,
            })
        errors.append({
            'id': error_id,
            'severity': severity,
            'message': message,
            'verbose': verbose,
            'locations': locations,
        })
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    return errors, {"by_severity": severity_counts}


def run_cppcheck(tus: List[Path], compile_db: Optional[Path], root: Path) -> Dict[str, Any]:
    binary = shutil.which("cppcheck")
    if not binary:
        return {
            "tool": "cppcheck",
            "ok": False,
            "status": "missing_binary",
            "message": "cppcheck not found on PATH",
        }

    if not compile_db or not compile_db.exists():
        return {
            "tool": "cppcheck",
            "ok": False,
            "status": "missing_compile_commands",
            "message": "compile_commands.json not found. Run llmtk context export or compile_db first.",
        }

    if not tus:
        return {
            "tool": "cppcheck",
            "ok": True,
            "status": "no_translation_units",
            "issues": [],
            "summary": {"by_severity": {}},
        }

    env = os.environ.copy()

    command = [
        binary,
        f"--project={compile_db}",
        "--xml",
        "--xml-version=2",
        "--enable=warning,style,performance,portability",
        "--inline-suppr",
        "--quiet",
    ]

    start = time.monotonic()
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    duration = time.monotonic() - start

    stdout_text = strip_ansi(proc.stdout)
    stderr_text = strip_ansi(proc.stderr)

    xml_start = stderr_text.find("<?xml")
    xml_fragment = stderr_text[xml_start:] if xml_start != -1 else ""

    issues, summary = parse_cppcheck_xml(xml_fragment, root)
    ok = proc.returncode == 0
    status = "completed" if ok else "completed_with_issues"
    return {
        "tool": "cppcheck",
        "ok": ok,
        "status": status,
        "exit_code": proc.returncode,
        "command": command,
        "issues": issues,
        "summary": summary,
        "duration_seconds": round(duration, 3),
        "stdout": limited_text(stdout_text),
        "stderr": limited_text(stderr_text),
    }


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: analyze.py <exports_dir> <compile_db> [paths...]")

    exports_dir = Path(sys.argv[1])
    compile_db_arg = sys.argv[2]
    filters = sys.argv[3:]

    root = Path(os.environ.get("LLMTK_PROJECT_ROOT", os.getcwd()))

    compile_db: Optional[Path]
    if compile_db_arg == "__NONE__":
        compile_db = None
    else:
        candidate = Path(compile_db_arg)
        compile_db = candidate if candidate.exists() else None

    tus = collect_translation_units(compile_db, filters, root)

    exports_dir.mkdir(parents=True, exist_ok=True)

    clang_tidy_report = run_clang_tidy(tus, compile_db, exports_dir, root)
    iwyu_report = run_iwyu(tus, compile_db, root)
    cppcheck_report = run_cppcheck(tus, compile_db, root)

    translations: List[str] = []
    for path in tus:
        try:
            translations.append(str(path.relative_to(root)))
        except ValueError:
            translations.append(str(path))

    shared_meta = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project_root": str(root),
        "filters": filters,
        "translation_units": translations,
        "compile_commands": str(compile_db) if compile_db else None,
    }

    def write_report(filename: str, payload: dict) -> None:
        payload.setdefault("meta", shared_meta)
        path = exports_dir / filename
        path.write_text(json.dumps(payload, indent=2))

    write_report("clang-tidy.json", clang_tidy_report)
    write_report("iwyu.json", iwyu_report)
    write_report("cppcheck.json", cppcheck_report)

    print(str(exports_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY
