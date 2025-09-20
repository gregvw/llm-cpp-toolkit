"""Capabilities command - generate machine-readable toolkit capabilities."""

import argparse
from ..core.context import get_exports_dir
from ..services.manifest import generate_capabilities_json

def cmd_capabilities(args: argparse.Namespace) -> int:
    """Execute the capabilities command."""
    path = generate_capabilities_json(get_exports_dir() / "capabilities.json")
    print(str(path))
    return 0

def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the capabilities command."""
    parser = subparsers.add_parser(
        "capabilities",
        help="Generate machine-readable toolkit capabilities summary"
    )
    parser.set_defaults(func=cmd_capabilities)