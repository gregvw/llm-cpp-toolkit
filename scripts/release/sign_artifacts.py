#!/usr/bin/env python3
"""Generate checksums and GPG signatures for release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from pathlib import Path
from typing import Iterable

SHA256_FILENAME = "SHA256SUMS"


def iter_artifacts(directory: Path, recursive: bool = False) -> Iterable[Path]:
    if recursive:
        yield from (p for p in directory.rglob("*") if p.is_file())
    else:
        yield from (p for p in directory.iterdir() if p.is_file())


def write_checksums(artifacts: Iterable[Path], output: Path) -> None:
    with output.open("w", encoding="utf-8") as fh:
        for artifact in sorted(artifacts):
            sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            fh.write(f"{sha}  {artifact.name}\n")
    print(f"✅ Wrote {output}")


def sign_file(path: Path, key_id: str | None = None) -> Path:
    sig_path = path.with_suffix(path.suffix + ".sig")
    cmd = ["gpg", "--armor", "--detach-sign", "--output", str(sig_path), str(path)]
    if key_id:
        cmd.insert(1, "--local-user")
        cmd.insert(2, key_id)
    subprocess.run(cmd, check=True)
    print(f"🔐 GPG signature created: {sig_path}")
    return sig_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing artifacts to sign")
    parser.add_argument("--recursive", action="store_true", help="Include nested files")
    parser.add_argument("--key", help="GPG key identifier for signing")
    parser.add_argument("--skip-sign", action="store_true", help="Only generate checksums")
    parser.add_argument("--output", type=Path, default=None, help="Path for the SHA256SUMS file")
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    directory = ns.directory.resolve()
    if not directory.is_dir():
        raise SystemExit(f"Artifact directory not found: {directory}")

    artifacts = [p for p in iter_artifacts(directory, ns.recursive) if p.name != SHA256_FILENAME]
    if not artifacts:
        raise SystemExit("No artifacts found to checksum")

    output = ns.output or (directory / SHA256_FILENAME)
    write_checksums(artifacts, output)

    if not ns.skip_sign:
        try:
            sign_file(output, key_id=ns.key)
        except FileNotFoundError:
            raise SystemExit("gpg executable not found; rerun with --skip-sign or install GnuPG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
