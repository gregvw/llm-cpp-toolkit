"""
Main orchestrator for llmtk preflight

Coordinates file discovery, delimiter checking, and syntax probing.
"""

import argparse
import pathlib
import sys
from typing import List, Optional, Set, Dict, Any
from dataclasses import dataclass

from .fileset import discover_files, should_check_file, get_supported_extensions
from .delimiters import get_delimiter_checker, check_markdown_fences
from .syntax_probes import get_syntax_probes, get_probe_for_file
from .reporters import Finding, output_json, output_sarif, output_human, determine_exit_code


@dataclass
class PreflightArgs:
    """Arguments for preflight execution."""
    diff_base: Optional[str] = None
    diff_target: Optional[str] = None
    since_ref: Optional[str] = None
    paths: Optional[List[str]] = None
    json_output: Optional[pathlib.Path] = None
    sarif_output: Optional[pathlib.Path] = None
    strict: bool = False
    max_lines: Optional[int] = None
    max_files: Optional[int] = None
    no_tree_sitter: bool = False
    no_syntax: bool = False
    extensions: Optional[Set[str]] = None
    verbose: bool = False


def check_file_delimiters(file_path: pathlib.Path, delimiter_checker) -> List[Finding]:
    """Check a single file for delimiter issues."""
    findings = []

    try:
        # Use the delimiter checker
        delimiter_findings = delimiter_checker.check_file(file_path)
        findings.extend(delimiter_findings)

        # Special handling for markdown files
        if file_path.suffix.lower() in {'.md', '.rst'}:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                markdown_findings = check_markdown_fences(file_path, content)
                findings.extend(markdown_findings)
            except Exception:
                pass  # Ignore read errors for markdown-specific checks

    except Exception as e:
        findings.append(Finding(
            file=str(file_path),
            line=1,
            col=1,
            rule="delimiter_check_error",
            symbol="",
            message=f"Error checking delimiters: {str(e)}",
            severity="warning"
        ))

    return findings


def check_file_syntax(file_path: pathlib.Path, syntax_probes) -> List[Finding]:
    """Check a single file for syntax issues using external probes."""
    probe = get_probe_for_file(file_path, syntax_probes)
    if not probe:
        return []

    try:
        return probe.check_file(file_path)
    except Exception as e:
        return [Finding(
            file=str(file_path),
            line=1,
            col=1,
            rule="syntax_check_error",
            symbol="",
            message=f"Error checking syntax: {str(e)}",
            severity="warning"
        )]


def should_skip_file_size(file_path: pathlib.Path, max_lines: Optional[int]) -> bool:
    """Check if file should be skipped due to size limits."""
    if not max_lines:
        return False

    try:
        # Quick line count check
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
        return line_count > max_lines
    except Exception:
        return False


def run_preflight(args: PreflightArgs) -> int:
    """
    Run the preflight checks and return exit code.

    Returns:
        0: No issues
        2: Warnings only (non-strict mode)
        3: Errors found
        10: Internal error
    """
    try:
        # Discover files to check
        if args.verbose:
            print("Discovering files...", file=sys.stderr)

        files = discover_files(
            diff_base=args.diff_base,
            diff_target=args.diff_target,
            since_ref=args.since_ref,
            explicit_paths=args.paths,
            include_working_changes=True,
            max_files=args.max_files,
            extensions=args.extensions
        )

        # Filter to supported files
        supported_files = [f for f in files if should_check_file(f)]

        # Apply size limits
        if args.max_lines:
            supported_files = [f for f in supported_files if not should_skip_file_size(f, args.max_lines)]

        if args.verbose:
            print(f"Found {len(supported_files)} files to check", file=sys.stderr)

        if not supported_files:
            if args.verbose:
                print("No files to check", file=sys.stderr)
            # Output empty results
            if args.json_output:
                output_json([], args.json_output)
            if args.sarif_output:
                output_sarif([], args.sarif_output)
            return 0

        all_findings: List[Finding] = []

        # Initialize checkers
        delimiter_checker = None if args.no_tree_sitter else get_delimiter_checker()
        syntax_probes = [] if args.no_syntax else get_syntax_probes()

        if args.verbose:
            print(f"Available syntax probes: {[type(p).__name__ for p in syntax_probes]}", file=sys.stderr)

        # Check each file
        for file_path in supported_files:
            if args.verbose:
                print(f"Checking {file_path}...", file=sys.stderr)

            file_findings: List[Finding] = []

            # Delimiter checking
            if delimiter_checker:
                delimiter_findings = check_file_delimiters(file_path, delimiter_checker)
                file_findings.extend(delimiter_findings)

            # Syntax checking
            if syntax_probes:
                syntax_findings = check_file_syntax(file_path, syntax_probes)
                file_findings.extend(syntax_findings)

            all_findings.extend(file_findings)

        # Generate outputs
        if args.json_output:
            output_json(all_findings, args.json_output)

        if args.sarif_output:
            output_sarif(all_findings, args.sarif_output)

        # Always output human-readable to stderr if there are findings
        if all_findings:
            output_human(all_findings, sys.stderr)
        elif args.verbose:
            print("✓ No issues found", file=sys.stderr)

        # Determine exit code
        return determine_exit_code(all_findings, args.strict)

    except Exception as e:
        print(f"Internal error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 10


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the argument parser for preflight."""
    parser = argparse.ArgumentParser(
        prog="llmtk preflight",
        description="Fast syntax and delimiter checking before build operations"
    )

    # File discovery options (mutually exclusive group)
    discovery_group = parser.add_mutually_exclusive_group()
    discovery_group.add_argument(
        "--diff",
        metavar="BASE_REF",
        help="Check files changed from BASE_REF (e.g., --diff HEAD~1)"
    )
    discovery_group.add_argument(
        "--since",
        metavar="REF",
        help="Check files changed since REF"
    )
    discovery_group.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH",
        help="Explicit paths to check"
    )

    # Output options
    parser.add_argument(
        "--json",
        metavar="FILE",
        type=pathlib.Path,
        help="Output findings as JSON to FILE"
    )
    parser.add_argument(
        "--sarif",
        metavar="FILE",
        type=pathlib.Path,
        help="Output findings as SARIF to FILE"
    )

    # Behavior options
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        metavar="N",
        help="Skip files with more than N lines"
    )
    parser.add_argument(
        "--max-files",
        type=int,
        metavar="N",
        help="Check at most N files"
    )

    # Feature toggles
    parser.add_argument(
        "--no-tree-sitter",
        action="store_true",
        help="Disable tree-sitter parsing (use fallback)"
    )
    parser.add_argument(
        "--no-syntax",
        action="store_true",
        help="Disable external syntax checking"
    )

    # Extensions filter
    parser.add_argument(
        "--extensions",
        metavar="EXT",
        nargs="+",
        help="Only check files with these extensions (e.g., .cpp .h)"
    )

    # Verbosity
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    return parser


def parse_args(argv: Optional[List[str]] = None) -> PreflightArgs:
    """Parse command line arguments."""
    parser = create_argument_parser()
    args = parser.parse_args(argv)

    # Handle --diff with optional target
    diff_base = None
    diff_target = None
    if args.diff:
        if '...' in args.diff:
            diff_base, diff_target = args.diff.split('...', 1)
        else:
            diff_base = args.diff

    # Convert extensions to set
    extensions = None
    if args.extensions:
        extensions = {ext if ext.startswith('.') else f'.{ext}' for ext in args.extensions}

    return PreflightArgs(
        diff_base=diff_base,
        diff_target=diff_target,
        since_ref=args.since,
        paths=args.paths,
        json_output=args.json,
        sarif_output=args.sarif,
        strict=args.strict,
        max_lines=args.max_lines,
        max_files=args.max_files,
        no_tree_sitter=args.no_tree_sitter,
        no_syntax=args.no_syntax,
        extensions=extensions,
        verbose=args.verbose
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for preflight."""
    args = parse_args(argv)
    return run_preflight(args)


if __name__ == "__main__":
    sys.exit(main())