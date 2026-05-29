"""Manifest loading and processing services."""

import datetime
import ast
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

    return load_minimal_yaml(path)


def load_minimal_yaml(path: pathlib.Path) -> Optional[Dict[str, Any]]:
    """Load the manifest subset needed for zero-dependency capabilities.

    This is intentionally small: it recognizes top-level manifest sections and
    simple scalar/list fields for each command/tool. Full nested schemas are
    loaded when PyYAML or yq is available.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    data: Dict[str, Any] = {}
    current_section: Optional[str] = None
    current_item: Optional[str] = None

    for raw_line in lines:
        line_without_comment = raw_line.split("#", 1)[0].rstrip()
        if not line_without_comment.strip():
            continue
        indent = len(line_without_comment) - len(line_without_comment.lstrip(" "))
        stripped = line_without_comment.strip()

        if indent == 0 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                data[key] = _parse_scalar(value)
                current_section = None
            else:
                data.setdefault(key, {})
                current_section = key
            current_item = None
            continue

        if current_section in {"tools", "commands"} and indent == 2 and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_item = key.strip()
            data.setdefault(current_section, {})[current_item] = {}
            value = value.strip()
            if value:
                data[current_section][current_item] = _parse_scalar(value)
            continue

        if current_section in {"tools", "commands"} and current_item and indent == 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                item = data.setdefault(current_section, {}).setdefault(current_item, {})
                if isinstance(item, dict):
                    item[key] = _parse_scalar(value)

    return data


def _parse_scalar(value: str) -> Any:
    """Parse a small YAML scalar/list value."""
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "None"}:
        return None
    if (value.startswith("[") and value.endswith("]")) or (value.startswith("{") and value.endswith("}")):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value

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
        "schema_version": 1,
        "_meta": {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "toolkit_version": get_version(),
            "tools_manifest": str(tools_manifest),
            "commands_manifest": str(commands_manifest),
            "stable_status": "supported",
        },
        "tools": {},
        "commands": {},
        "planned_commands": {},
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
            status = entry.get("status", "planned")
            payload = {
                "status": status,
                "description": entry.get("description"),
                "args": entry.get("args") or [],
                "runs": entry.get("runs") or [],
                "outputs": entry.get("outputs") or [],
                "json_summary": entry.get("json_summary"),
                "examples": entry.get("examples") or [],
            }
            if status == "supported":
                data["commands"][name] = payload
            else:
                data["planned_commands"][name] = payload

    write_json(out_path, data)
    return out_path
