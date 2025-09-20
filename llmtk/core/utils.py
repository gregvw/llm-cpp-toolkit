"""Common utility functions for llmtk."""

import json
import pathlib
import subprocess
from typing import Any, Dict, Optional
from .fs import safe_write_text
from .context import get_root

def run(cmd, cwd=None, check=True, env=None):
    """Run a command and return the result."""
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check, env=env)

def write_json(path: pathlib.Path, data: Any) -> None:
    """Write data as JSON to a file."""
    content = json.dumps(data, indent=2)
    safe_write_text(path, content)

def get_version() -> str:
    """Get the toolkit version."""
    try:
        vfile = get_root() / "VERSION"
        if vfile.exists():
            return vfile.read_text().strip()
    except Exception:
        pass
    try:
        res = subprocess.run(
            ["git", "-C", str(get_root()), "describe", "--tags", "--always"],
            text=True, capture_output=True, check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "0.0.0+unknown"