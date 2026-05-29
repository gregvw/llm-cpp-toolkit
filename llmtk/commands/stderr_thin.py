"""stderr-thin command implementation for llmtk."""

import argparse
import subprocess
import sys

from ..core.context import get_modules_dir, get_project_root
from ..core.dry_run import is_dry_run


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the stderr-thin command."""
    parser = subparsers.add_parser(
        "stderr-thin",
        help="Collapse compiler stderr into deterministic, budget-aware highlights"
    )

    parser.add_argument(
        "--log",
        help="Path to stderr log file to process"
    )

    parser.add_argument(
        "--compile",
        help="Substring filter for compile_commands.json entries"
    )

    parser.add_argument(
        "--compile-index",
        type=int,
        help="Explicit index into compile_commands.json"
    )

    parser.add_argument(
        "--level",
        choices=["summary", "focused", "detailed"],
        default="focused",
        help="Detail level (default: focused)"
    )

    parser.add_argument(
        "--context-budget",
        type=int,
        default=8000,
        help="Maximum characters in output (default: 8000)"
    )

    parser.add_argument(
        "--sarif",
        help="Output SARIF file path"
    )

    parser.add_argument(
        "--json",
        help="Output JSON file path"
    )

    parser.add_argument(
        "--text",
        help="Output text file path"
    )

    parser.add_argument(
        "command",
        nargs="*",
        help="Command to run and capture stderr from"
    )

    parser.set_defaults(func=handle_stderr_thin)


def handle_stderr_thin(args: argparse.Namespace) -> int:
    """Handle the stderr-thin command."""
    if is_dry_run():
        print("[DRY RUN] Would run stderr-thin with the following configuration:")
        print(f"  Log file: {args.log}")
        print(f"  Level: {args.level}")
        print(f"  Context budget: {args.context_budget}")
        print(f"  SARIF output: {args.sarif}")
        print(f"  Command: {' '.join(args.command) if args.command else 'None'}")
        return 0

    try:
        return run_stderr_thin(args)
    except Exception as e:
        print(f"Error running stderr-thin: {e}", file=sys.stderr)
        return 1


def run_stderr_thin(args: argparse.Namespace) -> int:
    """Run the stderr-thin processor."""
    project_root = get_project_root()
    stderr_thin_script = get_modules_dir() / "stderr_thin.py"

    if not stderr_thin_script.exists():
        print(f"Error: stderr-thin module not found at {stderr_thin_script}", file=sys.stderr)
        return 1

    # Build command for stderr_thin.py
    cmd = [sys.executable, str(stderr_thin_script)]

    # Add arguments
    if args.log:
        cmd.extend(["--log", args.log])
    if args.compile:
        cmd.extend(["--compile", args.compile])
    if args.compile_index is not None:
        cmd.extend(["--compile-index", str(args.compile_index)])
    if args.level:
        cmd.extend(["--level", args.level])
    if args.context_budget:
        cmd.extend(["--context-budget", str(args.context_budget)])
    if args.sarif:
        cmd.extend(["--sarif", args.sarif])
    if args.json:
        cmd.extend(["--json", args.json])
    if args.text:
        cmd.extend(["--text", args.text])

    try:
        # If we have a command to run, execute it and capture stderr
        if args.command:
            # Run the command and capture stderr
            result = subprocess.run(
                args.command,
                cwd=project_root,
                capture_output=True,
                text=True
            )

            # Feed stderr to stderr_thin via stdin
            thin_result = subprocess.run(
                cmd,
                input=result.stderr,
                cwd=project_root,
                capture_output=True,
                text=True
            )

            # Print stdout from both commands
            if result.stdout:
                print("Command output:", file=sys.stderr)
                print(result.stdout)

            if thin_result.stdout:
                print(thin_result.stdout)

            if thin_result.stderr:
                print(thin_result.stderr, file=sys.stderr)

            return thin_result.returncode

        else:
            # Run stderr_thin directly (will read from log file or stdin)
            result = subprocess.run(
                cmd,
                cwd=project_root,
                text=True
            )

            return result.returncode

    except FileNotFoundError:
        print(f"Error: stderr-thin script not found or not executable: {stderr_thin_script}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error running stderr-thin: {e}", file=sys.stderr)
        return 1
