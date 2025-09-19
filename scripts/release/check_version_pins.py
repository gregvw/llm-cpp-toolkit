#!/usr/bin/env python3
"""Validate that distribution metadata references the same llmtk version."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "VERSION"
HOMEBREW_FORMULA = ROOT / "homebrew" / "llm-cpp-toolkit.rb"
FLAKE_FILE = ROOT / "flake.nix"
DOCKERFILE = ROOT / "containers" / "Dockerfile"
RELEASE_MANIFEST = ROOT / "src" / "llmtk_bootstrap" / "data" / "releases.json"


class PinMismatch(Exception):
    pass


def read_version() -> str:
    return VERSION_FILE.read_text().strip()


def check_homebrew(version: str) -> None:
    content = HOMEBREW_FORMULA.read_text()
    match = re.search(r"/v([0-9]+\.[0-9]+\.[0-9]+)\.tar\.gz", content)
    if not match:
        raise PinMismatch("Homebrew formula missing versioned tarball URL")
    if match.group(1) != version:
        raise PinMismatch(f"Homebrew formula targets v{match.group(1)} but VERSION is {version}")


def check_flake(version: str) -> None:
    content = FLAKE_FILE.read_text()
    match = re.search(r"version = \"([^\"]+)\";", content)
    if not match:
        raise PinMismatch("flake.nix missing version attribute")
    if match.group(1) != version:
        raise PinMismatch(f"flake.nix version is {match.group(1)} but VERSION is {version}")


def check_dockerfile(version: str) -> None:
    content = DOCKERFILE.read_text()
    if f"pip install --no-cache-dir ." not in content:
        raise PinMismatch("Dockerfile does not install local package")
    if f"llmtk --bootstrap-info" not in content:
        raise PinMismatch("Dockerfile missing bootstrap smoke test")
    # Optionally ensure version comment? (no direct reference)


def check_release_manifest(version: str) -> None:
    data = json.loads(RELEASE_MANIFEST.read_text())
    entry = data.get(version)
    if not entry:
        raise PinMismatch(f"Release manifest missing entry for version {version}")
    url = entry.get("tarball_url", "")
    if f"v{version}" not in url:
        raise PinMismatch(f"Release manifest for {version} points to unexpected URL: {url}")
    sha = entry.get("sha256", "")
    if len(sha) != 64 or set(sha) == {"0"}:
        raise PinMismatch(f"Release manifest for {version} has invalid sha256: {sha}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    version = read_version()
    checks = [check_homebrew, check_flake, check_dockerfile, check_release_manifest]
    problems = []
    for check in checks:
        try:
            check(version)
        except FileNotFoundError as exc:
            problems.append(f"Missing file: {exc.filename}")
        except PinMismatch as exc:
            problems.append(str(exc))
    if problems:
        raise SystemExit("\n".join(["Pin alignment checks failed:"] + [f"  - {p}" for p in problems]))
    print(f"All pins aligned for version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
