import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import urllib.request
from dataclasses import dataclass
from importlib import resources
from importlib import metadata
from pathlib import Path
from typing import Optional

# Locations
DEFAULT_INSTALL_DIR = Path(os.environ.get("LLMTK_BOOTSTRAP_INSTALL", Path.home() / ".local" / "share" / "llm-cpp-toolkit"))
DEFAULT_CACHE_DIR = Path(os.environ.get("LLMTK_BOOTSTRAP_CACHE", Path.home() / ".cache" / "llm-cpp-toolkit"))
RELEASE_DATA_PACKAGE = "llmtk_bootstrap.data"
RELEASE_DATA_FILE = "releases.json"
SKIP_VERIFY = os.environ.get("LLMTK_BOOTSTRAP_SKIP_VERIFY") == "1"


@dataclass
class ReleaseDescriptor:
    version: str
    url: str
    sha256: str

    @property
    def short_sha(self) -> str:
        return self.sha256[:12]


class BootstrapError(RuntimeError):
    """Raised when the bootstrap process fails."""


def _load_release_manifest() -> dict:
    with resources.files(RELEASE_DATA_PACKAGE).joinpath(RELEASE_DATA_FILE).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _toolkit_version() -> str:
    try:
        return metadata.version("llm-cpp-toolkit")
    except metadata.PackageNotFoundError:  # running from source tree
        version_file = Path(__file__).resolve().parents[2] / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "0.0.0.dev0"


def _resolve_release(version: str, releases: dict) -> ReleaseDescriptor:
    data = releases.get(version)
    if not data:
        raise BootstrapError(
            textwrap.dedent(
                f"""
                Release metadata for version {version} is missing.
                Update src/llmtk_bootstrap/data/{RELEASE_DATA_FILE} before publishing.
                """.strip()
            )
        )
    url = data.get("tarball_url")
    sha = (data.get("sha256") or "").strip()
    if not url or not sha:
        raise BootstrapError(
            textwrap.dedent(
                f"""
                Release entry for {version} is incomplete.
                Expected keys: tarball_url, sha256 (64 hex characters).
                """.strip()
            )
        )
    if len(sha) != 64:
        raise BootstrapError(f"Invalid sha256 for release {version}: {sha}")
    return ReleaseDescriptor(version=version, url=url, sha256=sha)


def _download_release(rel: ReleaseDescriptor, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    tar_path = cache_dir / f"{rel.version}.tar.gz"
    if tar_path.exists():
        if SKIP_VERIFY or _verify_file(tar_path, rel.sha256):
            return tar_path
        tar_path.unlink()

    tmp_path = tar_path.with_suffix(".tmp")
    print(f"📦 Downloading llmtk release {rel.version} ({rel.short_sha})")
    with urllib.request.urlopen(rel.url) as response, open(tmp_path, "wb") as dst:
        hasher = hashlib.sha256()
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if not SKIP_VERIFY and digest != rel.sha256:
        tmp_path.unlink(missing_ok=True)
        raise BootstrapError(
            f"Checksum mismatch for {rel.url}\nExpected {rel.sha256}\nGot      {digest}"
        )
    tmp_path.rename(tar_path)
    return tar_path


def _verify_file(path: Path, expected_sha: str) -> bool:
    if not path.exists():
        return False
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest() == expected_sha


def _safe_extract(tar_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            target = dest_dir / member.name
            if not str(target.resolve()).startswith(str(dest_dir.resolve())):
                raise BootstrapError(f"Unsafe path detected in archive: {member.name}")
        archive.extractall(dest_dir)
    # Determine extracted root directory
    top_level = sorted(dest_dir.iterdir())
    if len(top_level) == 1 and top_level[0].is_dir():
        return top_level[0]
    return dest_dir


def _ensure_release_install(rel: ReleaseDescriptor, install_dir: Path, cache_dir: Path) -> Path:
    target = install_dir / rel.version
    marker = target / ".llmtk.ok"
    if marker.exists():
        return Path(marker.read_text().strip()).resolve()

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    tarball = _download_release(rel, cache_dir)
    with tempfile.TemporaryDirectory(prefix="llmtk-extract-", dir=str(target.parent)) as tmp:
        tmp_path = Path(tmp)
        extracted_root = _safe_extract(tarball, tmp_path)
        # Move into place
        for item in extracted_root.iterdir():
            shutil.move(str(item), target / item.name)
    root = _discover_root(target)
    marker.write_text(str(root.resolve()))
    (install_dir / "current").write_text(rel.version)
    return root


def _discover_root(directory: Path) -> Path:
    # Look for cli/llmtk script to anchor root
    for candidate in [directory] + [p for p in directory.iterdir() if p.is_dir()]:
        if (candidate / "cli" / "llmtk").exists():
            return candidate
    raise BootstrapError(f"Unable to locate llmtk root inside {directory}")


def _run_llmtk(root: Path, argv: list[str]) -> int:
    cli_path = root / "cli" / "llmtk"
    if not cli_path.exists():
        raise BootstrapError(f"llmtk executable missing at {cli_path}")
    env = os.environ.copy()
    env.setdefault("LLMTK_DIR", str(root))
    python_exe = env.get("LLMTK_BOOTSTRAP_PYTHON", sys.executable)
    cmd = [python_exe, str(cli_path)] + argv
    return subprocess.call(cmd, env=env)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="llmtk", add_help=False)
    parser.add_argument("--bootstrap-info", action="store_true", help="Print bootstrap diagnostic information")
    parser.add_argument("--force-reinstall", action="store_true", help="Redownload and reinstall the cached release")
    parser.add_argument("--install-dir", type=Path, default=DEFAULT_INSTALL_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--use-source", type=Path, help="Run llmtk from a local checkout (developer override)")
    parser.add_argument("--help", action="store_true", help="Show llmtk help (after bootstrap)")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    ns = parse_args(argv)
    version = _toolkit_version()
    if ns.use_source:
        root = ns.use_source.resolve()
        print(f"🛠️  Running llmtk from source at {root}")
        return _run_llmtk(root, ns.args)

    releases = _load_release_manifest()
    rel = _resolve_release(version, releases)

    if ns.force_reinstall:
        dest = ns.install_dir / rel.version
        if dest.exists():
            shutil.rmtree(dest)
            print(f"♻️  Cleared cached release at {dest}")

    try:
        root = _ensure_release_install(rel, ns.install_dir, ns.cache_dir)
    except BootstrapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if ns.bootstrap_info:
        print(json.dumps({
            "version": version,
            "install_dir": str(ns.install_dir),
            "cache_dir": str(ns.cache_dir),
            "root": str(root),
            "release": {
                "url": rel.url,
                "sha256": rel.sha256,
            },
        }, indent=2))
        return 0

    args = ns.args
    if ns.help and "--help" not in args:
        args = ["--help"] + args
    return _run_llmtk(root, args)


if __name__ == "__main__":
    sys.exit(main())
