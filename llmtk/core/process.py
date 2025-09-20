"""Process execution utilities for llmtk."""

import subprocess
import pathlib
import hashlib
from typing import Any, Dict, List, Optional
from ..types import CommandArgs

def hashed_workspace() -> str:
    """Generate a hash of the current workspace."""
    try:
        cwd = pathlib.Path.cwd()
        content = str(cwd.resolve())
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    except Exception:
        return "unknown"

def run_command(
    cmd: CommandArgs,
    *,
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
    cwd: Optional[pathlib.Path] = None,
    env: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> subprocess.CompletedProcess:
    """Run a command with consistent defaults."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=text,
        cwd=cwd,
        env=env,
        **kwargs
    )

def run_command_safe(
    cmd: CommandArgs,
    *,
    capture_output: bool = True,
    text: bool = True,
    cwd: Optional[pathlib.Path] = None,
    env: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> subprocess.CompletedProcess:
    """Run a command safely without raising on non-zero exit."""
    return subprocess.run(
        cmd,
        check=False,
        capture_output=capture_output,
        text=text,
        cwd=cwd,
        env=env,
        **kwargs
    )