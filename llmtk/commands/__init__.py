"""Command implementations for llmtk."""

from typing import Dict, Any, Callable
import argparse

# Command registry
_commands: Dict[str, Callable[[argparse.ArgumentParser], None]] = {}

def register_command(name: str, register_func: Callable[[argparse.ArgumentParser], None]) -> None:
    """Register a command with the CLI."""
    _commands[name] = register_func

def get_commands() -> Dict[str, Callable[[argparse.ArgumentParser], None]]:
    """Get all registered commands."""
    return _commands.copy()

def setup_commands(subparsers: argparse._SubParsersAction) -> None:
    """Set up all registered commands."""
    # Import and register commands
    from . import doctor, capabilities, telemetry
    doctor.register(subparsers)
    capabilities.register(subparsers)
    telemetry.register(subparsers)

    # Additional commands will be added incrementally