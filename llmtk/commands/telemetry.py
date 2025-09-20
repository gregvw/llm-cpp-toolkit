"""Telemetry command - manage telemetry settings."""

import argparse
import datetime
from ..core.config import (
    telemetry_state, telemetry_enabled, ensure_telemetry_id,
    save_user_config, get_user_config, TELEMETRY_FILE
)
from ..core.dry_run import is_dry_run, dry_run_notice

def cmd_telemetry(args: argparse.Namespace) -> int:
    """Execute the telemetry command."""
    action = getattr(args, "telemetry_action", "status")
    state = telemetry_state()
    timestamp = datetime.datetime.now(datetime.UTC).isoformat()

    if action == "status":
        status = "enabled" if telemetry_enabled() else "disabled"
        print(f"Telemetry is {status}.")
        if telemetry_enabled():
            print("Anonymous identifier:", state.get("id", "(pending)"))
            print(f"Events stored at: {TELEMETRY_FILE}")
        else:
            print("Enable telemetry with 'llmtk telemetry enable'.")
        if TELEMETRY_FILE.exists():
            print(f"Recorded events: {TELEMETRY_FILE}")
        else:
            print("No telemetry events recorded yet.")
        return 0

    if action == "enable":
        if telemetry_enabled():
            print("Telemetry already enabled.")
            return 0
        if is_dry_run():
            dry_run_notice("enable telemetry")
            print("Dry-run: telemetry remains disabled.")
            return 0
        state["enabled"] = True
        state["enabled_at"] = timestamp
        ensure_telemetry_id()
        save_user_config(get_user_config())
        print("Telemetry enabled. Events will be written locally in anonymized form.")
        print(f"Log file: {TELEMETRY_FILE}")
        return 0

    if action == "disable":
        if not telemetry_enabled():
            print("Telemetry already disabled.")
            return 0
        if is_dry_run():
            dry_run_notice("disable telemetry")
            print("Dry-run: telemetry remains enabled.")
            return 0
        state["enabled"] = False
        state["disabled_at"] = timestamp
        save_user_config(get_user_config())
        print("Telemetry disabled. Existing logs remain on disk until purged.")
        return 0

    if action == "purge":
        if is_dry_run():
            dry_run_notice(f"purge telemetry logs at {TELEMETRY_FILE}")
            print("Dry-run: telemetry logs not removed.")
            return 0
        if TELEMETRY_FILE.exists():
            TELEMETRY_FILE.unlink()
        user_config = get_user_config()
        user_config["telemetry"] = {}
        save_user_config(user_config)
        print("Telemetry preferences reset and logs purged.")
        return 0

    print(f"Unknown telemetry action: {action}")
    return 1

def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the telemetry command."""
    parser = subparsers.add_parser(
        "telemetry",
        help="Manage telemetry preferences"
    )
    parser.add_argument(
        "telemetry_action",
        choices=["status", "enable", "disable", "purge"],
        help="Telemetry action to perform"
    )
    parser.set_defaults(func=cmd_telemetry)