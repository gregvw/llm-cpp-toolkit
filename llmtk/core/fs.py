"""Safe filesystem operations for llmtk."""

import pathlib
import shutil
from .dry_run import is_dry_run, dry_run_notice

def safe_mkdir(path: pathlib.Path, *, parents: bool = False, exist_ok: bool = True) -> None:
    """Create a directory with dry-run support."""
    if is_dry_run():
        dry_run_notice(f"mkdir {path}")
        return
    path.mkdir(parents=parents, exist_ok=exist_ok)

def safe_write_text(path: pathlib.Path, content: str) -> None:
    """Write text to a file with dry-run support."""
    if is_dry_run():
        dry_run_notice(f"write {path} ({len(content.encode('utf-8'))} bytes)")
        return
    safe_mkdir(path.parent, parents=True, exist_ok=True)
    path.write_text(content)

def safe_write_bytes(path: pathlib.Path, content: bytes) -> None:
    """Write bytes to a file with dry-run support."""
    if is_dry_run():
        dry_run_notice(f"write {path} ({len(content)} bytes)")
        return
    safe_mkdir(path.parent, parents=True, exist_ok=True)
    path.write_bytes(content)

def safe_copy_file(src: pathlib.Path, dest: pathlib.Path) -> None:
    """Copy a file with dry-run support."""
    if is_dry_run():
        dry_run_notice(f"copy {src} -> {dest}")
        return
    safe_mkdir(dest.parent, parents=True, exist_ok=True)
    shutil.copy2(src, dest)

def safe_remove(path: pathlib.Path) -> None:
    """Remove a file or directory with dry-run support."""
    if not path.exists():
        return
    if is_dry_run():
        dry_run_notice(f"remove {path}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()