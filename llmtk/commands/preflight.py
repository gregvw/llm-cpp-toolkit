"""Preflight command wrapper for llmtk."""

import argparse
import sys
from pathlib import Path
from typing import List

from ..core.context import get_exports_dir, get_project_root
from ..core.dry_run import is_dry_run


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the preflight command."""
    parser = subparsers.add_parser(
        "preflight",
        help="Fast syntax and delimiter validation before expensive build operations",
    )

    discovery = parser.add_mutually_exclusive_group()
    discovery.add_argument("--diff", metavar="BASE_REF", help="Check files changed from BASE_REF")
    discovery.add_argument("--since", metavar="REF", help="Check files changed since REF")
    discovery.add_argument("--paths", nargs="+", metavar="PATH", help="Explicit paths to check")

    parser.add_argument("--json", metavar="FILE", type=Path, help="Output findings as JSON to FILE")
    parser.add_argument("--sarif", metavar="FILE", type=Path, help="Output findings as SARIF to FILE")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--max-lines", type=int, metavar="N", help="Skip files with more than N lines")
    parser.add_argument("--max-files", type=int, metavar="N", help="Check at most N files")
    parser.add_argument("--no-tree-sitter", action="store_true", help="Disable tree-sitter parsing")
    parser.add_argument("--no-syntax", action="store_true", help="Disable external syntax checking")
    parser.add_argument("--extensions", metavar="EXT", nargs="+", help="Only check these extensions")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    parser.set_defaults(func=handle_preflight)


def handle_preflight(args: argparse.Namespace) -> int:
    """Handle the preflight command."""
    if is_dry_run():
        print("[DRY RUN] Would run preflight with the following configuration:")
        print(f"  Diff: {args.diff}")
        print(f"  Since: {args.since}")
        print(f"  Paths: {args.paths}")
        print(f"  JSON: {args.json}")
        print(f"  SARIF: {args.sarif}")
        return 0

    argv = build_preflight_argv(args)
    try:
        from tools.preflight.main import main as preflight_main
    except Exception as exc:  # noqa: BLE001
        print(f"Error: preflight module is unavailable: {exc}", file=sys.stderr)
        return 10

    return preflight_main(argv)


def build_preflight_argv(args: argparse.Namespace) -> List[str]:
    """Translate llmtk argparse state into the preflight module argv."""
    argv: List[str] = []
    if args.diff:
        argv.extend(["--diff", args.diff])
    if args.since:
        argv.extend(["--since", args.since])
    if args.paths:
        argv.append("--paths")
        argv.extend(args.paths)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        argv.extend(["--json", str(args.json)])
    if args.sarif:
        args.sarif.parent.mkdir(parents=True, exist_ok=True)
        argv.extend(["--sarif", str(args.sarif)])
    if args.strict:
        argv.append("--strict")
    if args.max_lines is not None:
        argv.extend(["--max-lines", str(args.max_lines)])
    if args.max_files is not None:
        argv.extend(["--max-files", str(args.max_files)])
    if args.no_tree_sitter:
        argv.append("--no-tree-sitter")
    if args.no_syntax:
        argv.append("--no-syntax")
    if args.extensions:
        argv.append("--extensions")
        argv.extend(args.extensions)
    if args.verbose:
        argv.append("--verbose")
    return argv


def default_json_path() -> Path:
    """Return the default preflight JSON path for agent workflows."""
    return get_exports_dir() / "reports" / "preflight.json"


def run_preflight_for_agent(params: dict) -> int:
    """Run preflight from structured agent/MCP parameters."""
    args = argparse.Namespace(
        diff=params.get("diff"),
        since=params.get("since"),
        paths=params.get("paths"),
        json=Path(params.get("json") or default_json_path()),
        sarif=Path(params["sarif"]) if params.get("sarif") else None,
        strict=bool(params.get("strict", False)),
        max_lines=params.get("max_lines"),
        max_files=params.get("max_files"),
        no_tree_sitter=bool(params.get("no_tree_sitter", False)),
        no_syntax=bool(params.get("no_syntax", False)),
        extensions=params.get("extensions"),
        verbose=bool(params.get("verbose", False)),
    )
    if not args.diff and not args.since and not args.paths:
        args.paths = [str(get_project_root())]
    return handle_preflight(args)
