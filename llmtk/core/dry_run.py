"""Dry run infrastructure for llmtk."""

import subprocess
import shlex
from typing import Any, Sequence

# Global state
_ORIGINAL_SUBPROCESS_RUN = subprocess.run
_DRY_RUN = False

def format_cmd_for_display(cmd: Sequence[Any] | Any) -> str:
    """Format a command for display in dry-run output."""
    if isinstance(cmd, (list, tuple)):
        return " ".join(shlex.quote(str(part)) for part in cmd)
    return str(cmd)

def dry_run_notice(message: str) -> None:
    """Print a dry-run notice message."""
    print(f"[dry-run] {message}")

def _dry_run_subprocess(cmd, *args, **kwargs):  # type: ignore[override]
    """Mock subprocess.run for dry-run mode."""
    dry_run_notice(f"subprocess.run {format_cmd_for_display(cmd)}")
    capture_output = kwargs.get("capture_output", False)
    text_mode = kwargs.get("text", False)
    stdout = "" if capture_output or text_mode else None
    stderr = "" if capture_output or text_mode else None
    return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

def activate_dry_run() -> None:
    """Activate dry-run mode, replacing subprocess.run."""
    global _DRY_RUN
    if _DRY_RUN:
        return
    _DRY_RUN = True
    subprocess.run = _dry_run_subprocess  # type: ignore[assignment]

def deactivate_dry_run() -> None:
    """Deactivate dry-run mode, restoring original subprocess.run."""
    global _DRY_RUN
    if not _DRY_RUN:
        return
    subprocess.run = _ORIGINAL_SUBPROCESS_RUN  # type: ignore[assignment]
    _DRY_RUN = False

def is_dry_run() -> bool:
    """Check if dry-run mode is active."""
    return _DRY_RUN