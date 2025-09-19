#!/usr/bin/env python3
"""Entry point for strict CMake build helper."""

import sys
from pathlib import Path

# Ensure the modules directory is on sys.path when running from the repo root
repo_root = Path(__file__).resolve().parent.parent
modules_dir = repo_root / "modules"
if str(modules_dir) not in sys.path:
    sys.path.insert(0, str(modules_dir))

from strict_build import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
