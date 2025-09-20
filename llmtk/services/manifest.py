"""Manifest loading and processing services."""

import datetime
import json
import pathlib
import shutil
import subprocess
from typing import Any, Dict, Optional
from ..core.context import get_root
from ..core.utils import get_version, write_json

def load_yaml(path: pathlib.Path) -> Optional[Dict[str, Any]]:
    """Load YAML file using PyYAML or yq fallback."""
    # Try PyYAML first
    try:
        import yaml  # type: ignore
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    except Exception:
        pass

    # Fallback to yq if available
    if shutil.which("yq"):
        try:
            result = subprocess.run(
                ["yq", "-o=json", str(path)],
                text=True,
                capture_output=True,
                check=False
            )
            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout)
        except Exception:
            pass

    return None

def load_tools_manifest() -> Optional[Dict[str, Any]]:
    """Load the tools manifest."""
    tools_manifest = get_root() / "manifest" / "tools.yaml"
    if tools_manifest.exists():
        return load_yaml(tools_manifest)
    return None

def load_commands_manifest() -> Optional[Dict[str, Any]]:
    """Load the commands manifest."""
    commands_manifest = get_root() / "manifest" / "commands.yaml"
    if commands_manifest.exists():
        return load_yaml(commands_manifest)
    return None

def generate_capabilities_json(out_path: pathlib.Path) -> pathlib.Path:
    """Emit a machine-readable capabilities summary for agents."""
    tools_manifest = get_root() / "manifest" / "tools.yaml"
    commands_manifest = get_root() / "manifest" / "commands.yaml"
    tools = load_yaml(tools_manifest) or {}
    commands = load_yaml(commands_manifest) or {}

    data = {
        "$schema": f"https://llmtk.ai/schemas/capabilities-v1.json",
        "_meta": {
            "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "toolkit_version": get_version(),
            "tools_manifest": str(tools_manifest),
            "commands_manifest": str(commands_manifest),
        },
        "tools": {},
        "commands": {},
    }

    tools_section = tools.get("tools") if isinstance(tools, dict) else None
    if isinstance(tools_section, dict):
        for name, entry in tools_section.items():
            entry = entry or {}
            data["tools"][name] = {
                "version": entry.get("version"),
                "min_version": entry.get("min_version"),
                "provides": entry.get("provides") or [],
                "role": entry.get("role", "optional"),
                "invocation": entry.get("invocation") or {},
                "install": entry.get("install") or {},
                "check": entry.get("check") or {},
                "fallbacks": entry.get("fallbacks") or [],
                "local_install": entry.get("local_install") or None,
            }

    commands_section = commands.get("commands") if isinstance(commands, dict) else None
    if isinstance(commands_section, dict):
        for name, entry in commands_section.items():
            entry = entry or {}
            data["commands"][name] = {
                "description": entry.get("description"),
                "args": entry.get("args") or [],
                "runs": entry.get("runs") or [],
                "outputs": entry.get("outputs") or [],
                "json_summary": entry.get("json_summary"),
                "examples": entry.get("examples") or [],
            }

    write_json(out_path, data)
    return out_path