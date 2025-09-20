"""Main CLI entry point for llmtk."""

import argparse
import sys
from .core.dry_run import activate_dry_run
from .commands import setup_commands

def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="llmtk",
        description="LLM C++ Toolkit - AI-assisted C++ development tools"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without executing them"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="llmtk 1.0.0"
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=True
    )

    # Register all commands
    setup_commands(subparsers)

    return parser

def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Activate dry-run mode if requested
    if args.dry_run:
        activate_dry_run()

    # Execute the command
    try:
        return args.func(args)
    except AttributeError:
        # No command function set (shouldn't happen with required=True)
        parser.print_help()
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())