"""Configuration and telemetry management for llmtk."""

import json
import os
import pathlib
import sys
import datetime
import uuid
from typing import Any, Dict
from .dry_run import is_dry_run, dry_run_notice

def _resolve_dir(env_var: str, xdg_var: str, subdir: str) -> pathlib.Path:
    """Resolve XDG-compliant directory paths."""
    if env := os.environ.get(env_var):
        return pathlib.Path(env).expanduser()
    if xdg := os.environ.get(xdg_var):
        return pathlib.Path(xdg).expanduser() / subdir
    return pathlib.Path.home() / (".config" if xdg_var == "XDG_CONFIG_HOME" else ".local/share") / subdir

# Global paths
CONFIG_DIR = _resolve_dir("LLMTK_CONFIG_HOME", "XDG_CONFIG_HOME", "llmtk")
DATA_DIR = _resolve_dir("LLMTK_DATA_HOME", "XDG_DATA_HOME", "llmtk")
CONFIG_FILE = CONFIG_DIR / "config.json"
TELEMETRY_FILE = DATA_DIR / "telemetry.jsonl"

# Global config cache
_USER_CONFIG: Dict[str, Any] = {}

def load_user_config() -> Dict[str, Any]:
    """Load user configuration from disk."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        print(f"Warning: Failed to parse {CONFIG_FILE}: {exc}", file=sys.stderr)
        return {}
    except Exception as exc:
        print(f"Warning: Could not load config {CONFIG_FILE}: {exc}", file=sys.stderr)
        return {}

def save_user_config(config: Dict[str, Any]) -> None:
    """Save user configuration to disk."""
    if is_dry_run():
        dry_run_notice(f"update config {CONFIG_FILE}")
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

def get_user_config() -> Dict[str, Any]:
    """Get the cached user configuration."""
    global _USER_CONFIG
    if not _USER_CONFIG:
        _USER_CONFIG = load_user_config()
    return _USER_CONFIG

def get_config_value(key: str, default: Any = None) -> Any:
    """Get a configuration value."""
    return get_user_config().get(key, default)

def update_config_value(key: str, value: Any) -> None:
    """Update a configuration value."""
    config = get_user_config()
    config[key] = value
    save_user_config(config)

def telemetry_state() -> Dict[str, Any]:
    """Get telemetry configuration state."""
    return get_user_config().setdefault("telemetry", {})

def telemetry_enabled() -> bool:
    """Check if telemetry is enabled."""
    return bool(telemetry_state().get("enabled", False))

def ensure_telemetry_id() -> str:
    """Ensure a telemetry ID exists."""
    state = telemetry_state()
    if "id" not in state:
        state["id"] = uuid.uuid4().hex
        state["enabled"] = state.get("enabled", False)
        state["created"] = datetime.datetime.now(datetime.UTC).isoformat()
        save_user_config(get_user_config())
    return state["id"]

def record_telemetry(event: Dict[str, Any]) -> None:
    """Record a telemetry event."""
    if not telemetry_enabled():
        return
    event = dict(event)
    event["telemetry_id"] = ensure_telemetry_id()
    if is_dry_run():
        dry_run_notice("telemetry event (suppressed write)")
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, separators=(",", ":"))
    with open(TELEMETRY_FILE, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")