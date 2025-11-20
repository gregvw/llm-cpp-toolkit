"""SARIF validation utilities for testing."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def validate_sarif_structure(sarif_doc: Dict[str, Any]) -> List[str]:
    """
    Validate basic SARIF document structure.

    Returns a list of validation errors (empty list if valid).
    """
    errors = []

    # Check version
    if "version" not in sarif_doc:
        errors.append("Missing required field: version")
    elif sarif_doc["version"] != "2.1.0":
        errors.append(f"Invalid SARIF version: {sarif_doc['version']} (expected 2.1.0)")

    # Check schema
    if "$schema" not in sarif_doc:
        errors.append("Missing required field: $schema")

    # Check runs
    if "runs" not in sarif_doc:
        errors.append("Missing required field: runs")
    elif not isinstance(sarif_doc["runs"], list):
        errors.append("Field 'runs' must be an array")
    else:
        # Validate each run
        for idx, run in enumerate(sarif_doc["runs"]):
            run_errors = validate_sarif_run(run, idx)
            errors.extend(run_errors)

    return errors


def validate_sarif_run(run: Dict[str, Any], run_idx: int) -> List[str]:
    """Validate a SARIF run structure."""
    errors = []
    prefix = f"Run[{run_idx}]"

    # Check tool
    if "tool" not in run:
        errors.append(f"{prefix}: Missing required field: tool")
    else:
        if "driver" not in run["tool"]:
            errors.append(f"{prefix}: Missing required field: tool.driver")
        else:
            driver = run["tool"]["driver"]
            if "name" not in driver:
                errors.append(f"{prefix}: Missing required field: tool.driver.name")

    # Check results (optional but should be a list if present)
    if "results" in run and not isinstance(run["results"], list):
        errors.append(f"{prefix}: Field 'results' must be an array")

    return errors


def validate_sarif_result(result: Dict[str, Any], result_idx: int) -> List[str]:
    """Validate a SARIF result structure."""
    errors = []
    prefix = f"Result[{result_idx}]"

    # Check ruleId (recommended)
    if "ruleId" not in result:
        errors.append(f"{prefix}: Missing recommended field: ruleId")

    # Check message
    if "message" not in result:
        errors.append(f"{prefix}: Missing required field: message")
    elif not isinstance(result["message"], dict):
        errors.append(f"{prefix}: Field 'message' must be an object")
    elif "text" not in result["message"]:
        errors.append(f"{prefix}: Missing required field: message.text")

    # Check level (optional, but should be valid if present)
    if "level" in result:
        valid_levels = ["none", "note", "warning", "error"]
        if result["level"] not in valid_levels:
            errors.append(f"{prefix}: Invalid level: {result['level']} (must be one of {valid_levels})")

    # Check locations (optional, but should be valid if present)
    if "locations" in result:
        if not isinstance(result["locations"], list):
            errors.append(f"{prefix}: Field 'locations' must be an array")

    return errors


def count_sarif_results(sarif_doc: Dict[str, Any]) -> int:
    """Count total results across all runs in a SARIF document."""
    total = 0
    for run in sarif_doc.get("runs", []):
        total += len(run.get("results", []))
    return total


def get_sarif_statistics(sarif_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get statistics about a SARIF document.

    Returns a dictionary with counts and breakdowns.
    """
    stats = {
        "total_runs": len(sarif_doc.get("runs", [])),
        "total_results": 0,
        "results_by_level": {},
        "results_by_rule": {},
        "unique_files": set(),
        "tools": []
    }

    for run in sarif_doc.get("runs", []):
        # Get tool name
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "unknown")
        stats["tools"].append(tool_name)

        # Count results
        results = run.get("results", [])
        stats["total_results"] += len(results)

        for result in results:
            # Count by level
            level = result.get("level", "warning")
            stats["results_by_level"][level] = stats["results_by_level"].get(level, 0) + 1

            # Count by rule
            rule_id = result.get("ruleId", "unknown")
            stats["results_by_rule"][rule_id] = stats["results_by_rule"].get(rule_id, 0) + 1

            # Track unique files
            for location in result.get("locations", []):
                phys_loc = location.get("physicalLocation", {})
                uri = phys_loc.get("artifactLocation", {}).get("uri", "")
                if uri:
                    stats["unique_files"].add(uri)

    stats["unique_files"] = len(stats["unique_files"])
    return stats


def load_sarif_fixture(fixture_name: str, fixtures_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load a SARIF fixture file for testing.

    Args:
        fixture_name: Name of the fixture file (e.g., "analysis.sarif")
        fixtures_dir: Directory containing fixtures (defaults to tests/fixtures/expected_outputs)

    Returns:
        Parsed SARIF document
    """
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "expected_outputs"

    fixture_path = fixtures_dir / fixture_name
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path) as f:
        return json.load(f)


def assert_sarif_valid(sarif_doc: Dict[str, Any]) -> None:
    """
    Assert that a SARIF document is valid (raises AssertionError if not).

    Use in tests like:
        assert_sarif_valid(my_sarif_doc)
    """
    errors = validate_sarif_structure(sarif_doc)
    if errors:
        error_msg = "\n".join(f"  - {err}" for err in errors)
        raise AssertionError(f"SARIF validation failed:\n{error_msg}")


def assert_sarif_has_results(sarif_doc: Dict[str, Any], min_count: int = 1) -> None:
    """Assert that a SARIF document has at least min_count results."""
    total = count_sarif_results(sarif_doc)
    assert total >= min_count, f"Expected at least {min_count} results, found {total}"


def assert_sarif_has_run(sarif_doc: Dict[str, Any], tool_name: str) -> None:
    """Assert that a SARIF document has a run from the specified tool."""
    tools = [run.get("tool", {}).get("driver", {}).get("name") for run in sarif_doc.get("runs", [])]
    assert tool_name in tools, f"Tool '{tool_name}' not found in runs. Found: {tools}"
