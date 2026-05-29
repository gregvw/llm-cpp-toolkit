"""Analysis command implementation for llmtk."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from ..core.context import get_modules_dir, get_project_root
from ..core.dry_run import is_dry_run


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the analyze command."""
    parser = subparsers.add_parser(
        "analyze",
        help="Run clang-tidy + IWYU + cppcheck with JSON reports"
    )

    parser.add_argument(
        "paths",
        nargs="*",
        help="Paths to analyze (default: src include .)"
    )

    parser.add_argument(
        "--sarif",
        action="store_true",
        help="Output results in SARIF format"
    )

    parser.set_defaults(func=handle_analyze)


def handle_analyze(args: argparse.Namespace) -> int:
    """Handle the analyze command."""
    if is_dry_run():
        print("[DRY RUN] Would run analysis with the following configuration:")
        print(f"  Paths: {args.paths or ['src', 'include', '.']}")
        print(f"  SARIF output: {args.sarif}")
        return 0

    try:
        return run_analyze(args.paths, args.sarif)
    except Exception as e:
        print(f"Error running analysis: {e}", file=sys.stderr)
        return 1


def run_analyze(paths: Optional[List[str]] = None, sarif: bool = False) -> int:
    """Run the analysis pipeline."""
    project_root = get_project_root()

    # Set up environment
    env = os.environ.copy()
    env["LLMTK_PROJECT_ROOT"] = str(project_root)

    # Use analyze.sh for the core analysis
    analyze_script = get_modules_dir() / "analyze.sh"
    if not analyze_script.exists():
        print(f"Error: analyze script not found at {analyze_script}", file=sys.stderr)
        return 1

    # Build command
    cmd = [str(analyze_script)]
    if paths:
        cmd.extend(paths)

    # Run the analysis
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True
        )

        # Print output from analyze.sh
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)

        # If analysis succeeded and SARIF is requested, convert to SARIF
        if result.returncode == 0 and sarif:
            return_code = convert_to_sarif(project_root)
            if return_code != 0:
                return return_code

        return result.returncode

    except FileNotFoundError:
        print(f"Error: analyze script not found or not executable: {analyze_script}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error running analysis: {e}", file=sys.stderr)
        return 1


def convert_to_sarif(project_root: Path) -> int:
    """Convert analysis results to SARIF format."""
    reports_dir = project_root / "exports" / "reports"
    sarif_converter = get_modules_dir() / "sarif_converter.py"

    if not sarif_converter.exists():
        print(f"Error: SARIF converter not found at {sarif_converter}", file=sys.stderr)
        return 1

    # Paths to analysis reports
    clang_tidy_path = reports_dir / "clang-tidy.json"
    cppcheck_path = reports_dir / "cppcheck.json"
    iwyu_path = reports_dir / "iwyu.json"
    sarif_output_path = reports_dir / "analysis.sarif"

    # Build command for SARIF converter
    cmd = [
        sys.executable,
        str(sarif_converter),
        str(sarif_output_path)
    ]

    # Add report paths if they exist (pass empty string for missing reports)
    cmd.append(str(clang_tidy_path) if clang_tidy_path.exists() else "")
    cmd.append(str(cppcheck_path) if cppcheck_path.exists() else "")
    cmd.append(str(iwyu_path) if iwyu_path.exists() else "")

    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"SARIF report generated: {sarif_output_path}")
        else:
            print(f"Error generating SARIF report: {result.stderr}", file=sys.stderr)

        return result.returncode

    except Exception as e:
        print(f"Error running SARIF converter: {e}", file=sys.stderr)
        return 1
