"""Global context and path management for llmtk."""

import pathlib

# Global paths - these mirror the original globals in cli/llmtk
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = pathlib.Path.cwd().resolve()
MODULES = ROOT / "modules"
EXPORTS = pathlib.Path.cwd() / "exports"

def get_root() -> pathlib.Path:
    """Get the toolkit root directory."""
    return ROOT

def get_project_root() -> pathlib.Path:
    """Get the current project root directory."""
    return PROJECT_ROOT

def get_modules_dir() -> pathlib.Path:
    """Get the modules directory."""
    return MODULES

def get_exports_dir() -> pathlib.Path:
    """Get the exports directory."""
    return EXPORTS

def set_exports_dir(path: pathlib.Path) -> None:
    """Set the exports directory (for testing)."""
    global EXPORTS
    EXPORTS = path