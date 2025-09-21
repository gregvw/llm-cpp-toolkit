"""Install command - install missing tools using manifest-driven approach."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..core.context import get_root, get_exports_dir
from ..core.utils import run
from ..core.fs import safe_mkdir
from ..services.manifest import load_tools_manifest
from .doctor import cmd_doctor


def detect_package_manager() -> Optional[str]:
    """Detect available package manager."""
    managers = [
        ("apt", ["apt-get", "apt"]),
        ("dnf", ["dnf"]),
        ("pacman", ["pacman"]),
        ("brew", ["brew"]),
        ("nix", ["nix-env"])
    ]

    for name, commands in managers:
        for cmd in commands:
            if shutil.which(cmd):
                return name
    return None


def install_tool_with_package_manager(tool_name: str, tool_config: Dict[str, Any], pm: str) -> bool:
    """Install a tool using system package manager."""
    if "install" not in tool_config or pm not in tool_config["install"]:
        return False

    packages = tool_config["install"][pm]
    if not packages:
        return False

    print(f"  📦 Installing {tool_name} via {pm}...")

    # Build install command based on package manager
    if pm == "apt":
        cmd = ["sudo", "apt-get", "update", "&&", "sudo", "apt-get", "install", "-y"] + packages
    elif pm == "dnf":
        cmd = ["sudo", "dnf", "install", "-y"] + packages
    elif pm == "pacman":
        cmd = ["sudo", "pacman", "-S", "--noconfirm"] + packages
    elif pm == "brew":
        cmd = ["brew", "install"] + packages
    elif pm == "nix":
        cmd = ["nix-env", "-iA"] + [f"nixpkgs.{pkg}" for pkg in packages]
    else:
        return False

    try:
        if pm == "apt":
            # Handle apt's compound command - allow interactive sudo
            print(f"    🔄 Updating package cache...")
            update_result = subprocess.run(["sudo", "apt-get", "update"],
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.PIPE)
            if update_result.returncode != 0:
                stderr_msg = update_result.stderr.decode() if update_result.stderr else 'Unknown error'
                # Only fail if it's a critical error, not just GPG warnings
                if "NO_PUBKEY" in stderr_msg or "not signed" in stderr_msg:
                    print(f"    ⚠️ apt update had warnings (ignoring): Repository signature issues")
                    print(f"    🔄 Proceeding with installation anyway...")
                else:
                    print(f"    ❌ apt update failed: {stderr_msg}")
                    return False

            print(f"    🔄 Installing packages: {' '.join(packages)}")
            install_result = subprocess.run(["sudo", "apt-get", "install", "-y"] + packages)
            if install_result.returncode == 0:
                print(f"    ✅ {tool_name} installed successfully")
                return True
            else:
                print(f"    ❌ Installation failed")
                return False
        else:
            # For non-apt package managers, run the full command allowing interaction
            result = subprocess.run(cmd, text=True)
            if result.returncode == 0:
                print(f"    ✅ {tool_name} installed successfully")
                return True
            else:
                print(f"    ❌ Installation failed")
                return False
    except subprocess.SubprocessError as e:
        print(f"    ❌ Installation failed: {e}")
        return False


def install_tool_locally(tool_name: str, tool_config: Dict[str, Any], local_bin: Path) -> bool:
    """Install a tool locally."""
    if "local_install" not in tool_config:
        print(f"    ❌ No local install method for {tool_name}")
        return False

    print(f"  🔧 Installing {tool_name} locally...")
    local_config = tool_config["local_install"]

    if "github_repo" in local_config:
        success = install_from_github(tool_name, tool_config, local_bin)
        if success:
            print(f"    ✅ {tool_name} installed locally")
        else:
            print(f"    ❌ Failed to install {tool_name} locally")
        return success

    return False


def install_from_github(tool_name: str, config: Dict[str, Any], local_bin: Path) -> bool:
    """Install tool from GitHub releases using manifest configuration."""
    local_config = config.get("local_install", {})
    repo = local_config.get("github_repo")

    if not repo:
        print(f"No GitHub repo specified for {tool_name}")
        return False

    print(f"Installing {tool_name} locally from {repo}")

    # Use the enhanced local installer with manifest data
    modules_dir = get_root() / "modules"
    enhanced_installer = modules_dir / "enhanced-install.sh"

    if enhanced_installer.exists():
        # Pass manifest data as environment variables
        env = os.environ.copy()
        env.update({
            "LLMTK_TOOL_NAME": tool_name,
            "LLMTK_GITHUB_REPO": repo,
            "LLMTK_RELEASE_PATTERN": local_config.get("release_pattern", ""),
            "LLMTK_BINARY_PATH": local_config.get("binary_path", ""),
            "LLMTK_BUILD_METHOD": local_config.get("build_method", ""),
            "LLMTK_LOCAL_BIN": str(local_bin),
            "LLMTK_MANIFEST_DATA": json.dumps(local_config)
        })

        # Add checksums as JSON
        if "checksums" in local_config:
            env["LLMTK_CHECKSUMS"] = json.dumps(local_config["checksums"])

        # Add version tag if specified
        if "version_tag" in local_config:
            env["LLMTK_VERSION_TAG"] = local_config["version_tag"]

        try:
            result = subprocess.run(
                [str(enhanced_installer)],
                env=env,
                text=True,
                capture_output=True,
                check=False
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    # Fallback to simple installer for specific tools
    return install_tool_basic(tool_name, local_bin)


def install_tool_basic(tool_name: str, local_bin: Path) -> bool:
    """Basic fallback installation for specific tools."""
    modules_dir = get_root() / "modules"
    script = modules_dir / "simple-install.sh"

    if tool_name in ["cppcheck", "include-what-you-use"] and script.exists():
        try:
            result = subprocess.run([str(script)], check=False)
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    return False


def cmd_install(args: argparse.Namespace) -> int:
    """Install missing tools using manifest-driven approach."""
    tools_manifest_path = get_root() / "manifest" / "tools.yaml"
    if not tools_manifest_path.exists():
        print(f"Error: Tools manifest not found at {tools_manifest_path}")
        return 1

    # Load tools manifest
    tools_config = load_tools_manifest()
    if not tools_config or "tools" not in tools_config:
        print("Error: Invalid tools manifest")
        return 1

    # Determine installation method
    use_local = getattr(args, 'local', False)
    pm = None if use_local else detect_package_manager()

    if not use_local and not pm:
        print("No package manager detected, falling back to local installation")
        use_local = True

    # Prepare local bin directory
    local_bin = get_root() / ".llmtk" / "bin"
    safe_mkdir(local_bin, parents=True, exist_ok=True)

    # Install missing tools
    tools_to_install = []
    if hasattr(args, 'tools') and args.tools:
        tools_to_install = args.tools
    else:
        # Install all core and recommended tools that are missing
        for tool_name, tool_config in tools_config["tools"].items():
            if tool_config.get("role") in ["core", "recommended"]:
                # Get the actual command to check from the manifest
                actual_cmd = tool_name
                check_config = tool_config.get("check", {})
                if isinstance(check_config, dict) and "cmd" in check_config:
                    actual_cmd = check_config["cmd"][0]  # First element is the command name

                if not shutil.which(actual_cmd):
                    tools_to_install.append(tool_name)

    if not tools_to_install:
        print("All tools are already installed")
        # Create a namespace object that mimics args but marks it as from install
        doctor_args = argparse.Namespace()
        doctor_args._from_install = True
        cmd_doctor(doctor_args)
        return 0

    print(f"🚀 Installing {len(tools_to_install)} missing tools...")
    print(f"   Method: {'local' if use_local else f'package manager ({pm})'}")
    print()

    installed = []
    failed = []
    skipped = []

    for tool_name in tools_to_install:
        if tool_name not in tools_config["tools"]:
            print(f"⚠️ {tool_name} not found in manifest, skipping")
            skipped.append(tool_name)
            continue

        tool_config = tools_config["tools"][tool_name]

        if use_local:
            if install_tool_locally(tool_name, tool_config, local_bin):
                installed.append(tool_name)
            else:
                # Fall back to simple installer for specific tools
                if tool_name in ["cppcheck", "include-what-you-use"]:
                    modules_dir = get_root() / "modules"
                    script = modules_dir / "simple-install.sh"
                    if script.exists():
                        print(f"  🔄 Using fallback installer for {tool_name}")
                        result = subprocess.run([str(script)], check=False)
                        if result.returncode == 0:
                            installed.append(tool_name)
                        else:
                            failed.append(tool_name)
                    else:
                        failed.append(tool_name)
                else:
                    failed.append(tool_name)
        else:
            if install_tool_with_package_manager(tool_name, tool_config, pm):
                installed.append(tool_name)
            else:
                print(f"  🔄 Falling back to local install for {tool_name}")
                if install_tool_locally(tool_name, tool_config, local_bin):
                    installed.append(tool_name)
                else:
                    failed.append(tool_name)

    # Update PATH for doctor check
    if local_bin.exists():
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{local_bin}:{old_path}"

    # Print comprehensive summary
    print()
    print("=" * 60)
    print("📊 INSTALLATION SUMMARY")
    print("=" * 60)

    if installed:
        print(f"✅ Successfully installed ({len(installed)}):")
        for tool in installed:
            print(f"   • {tool}")

    if failed:
        print(f"\n❌ Failed to install ({len(failed)}):")
        for tool in failed:
            print(f"   • {tool}")

    if skipped:
        print(f"\n⚠️ Skipped ({len(skipped)}):")
        for tool in skipped:
            print(f"   • {tool}")

    print()
    print("🏥 Updated system health check:")

    # Create a namespace object that mimics args but marks it as from install
    doctor_args = argparse.Namespace()
    doctor_args._from_install = True
    cmd_doctor(doctor_args)

    return 0 if not failed else 1


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the install command."""
    parser = subparsers.add_parser(
        "install",
        help="Install missing tools using manifest configuration"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force local installation (no sudo)"
    )
    parser.add_argument(
        "tools",
        nargs="*",
        help="Specific tools to install (default: all missing core/recommended tools)"
    )
    parser.set_defaults(func=cmd_install)