#!/usr/bin/env python3
"""SARIF merge utility for deduplicating and combining analysis results.

Provides functionality to merge multiple SARIF files and deduplicate results
based on rule ID, file location, and message content.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def compute_result_hash(result: Dict[str, Any]) -> str:
    """Compute a hash for a SARIF result to enable deduplication."""
    # Extract key identifying information
    rule_id = result.get("ruleId", "")
    message = result.get("message", {}).get("text", "")

    # Get primary location
    locations = result.get("locations", [])
    if locations:
        loc = locations[0]
        phys_loc = loc.get("physicalLocation", {})
        artifact = phys_loc.get("artifactLocation", {}).get("uri", "")
        region = phys_loc.get("region", {})
        line = region.get("startLine", 0)
        column = region.get("startColumn", 0)
    else:
        artifact = ""
        line = 0
        column = 0

    # Create hash from identifying information
    hash_input = f"{rule_id}:{artifact}:{line}:{column}:{message}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def deduplicate_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate results from a list."""
    seen_hashes: Set[str] = set()
    deduplicated = []

    for result in results:
        result_hash = compute_result_hash(result)
        if result_hash not in seen_hashes:
            seen_hashes.add(result_hash)
            deduplicated.append(result)

    return deduplicated


def merge_rules(runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Merge and deduplicate rules from multiple runs."""
    merged_rules = {}

    for run in runs:
        driver = run.get("tool", {}).get("driver", {})
        rules = driver.get("rules", [])

        for rule in rules:
            rule_id = rule.get("id")
            if rule_id and rule_id not in merged_rules:
                merged_rules[rule_id] = rule

    return merged_rules


def merge_artifacts(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge and deduplicate artifacts from multiple runs."""
    seen_uris: Set[str] = set()
    merged_artifacts = []

    for run in runs:
        artifacts = run.get("artifacts", [])
        for artifact in artifacts:
            uri = artifact.get("location", {}).get("uri", "")
            if uri and uri not in seen_uris:
                seen_uris.add(uri)
                merged_artifacts.append(artifact)

    return merged_artifacts


def create_merged_run(runs: List[Dict[str, Any]], run_id: str = "merged") -> Dict[str, Any]:
    """Create a single merged run from multiple runs."""
    if not runs:
        return {}

    # Collect all results
    all_results = []
    tool_names = []

    for run in runs:
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "unknown")
        tool_names.append(tool_name)
        all_results.extend(run.get("results", []))

    # Deduplicate results
    deduplicated_results = deduplicate_results(all_results)

    # Merge rules and artifacts
    merged_rules = merge_rules(runs)
    merged_artifacts = merge_artifacts(runs)

    # Create merged run
    merged_run = {
        "tool": {
            "driver": {
                "name": f"llmtk-analysis",
                "version": "1.0.0",
                "informationUri": "https://github.com/gregvw/llm-cpp-toolkit",
                "shortDescription": {"text": "LLM C++ Toolkit merged analysis"},
                "fullDescription": {"text": f"Combined analysis from: {', '.join(set(tool_names))}"},
                "rules": list(merged_rules.values())
            }
        },
        "results": deduplicated_results,
        "artifacts": merged_artifacts,
        "invocations": [{
            "executionSuccessful": True,
            "toolExecutionNotifications": [
                {
                    "message": {"text": f"Merged results from {len(runs)} analysis runs"},
                    "level": "note"
                }
            ]
        }]
    }

    return merged_run


def merge_sarif_files(*file_paths: Path, output_path: Path = None) -> Dict[str, Any]:
    """Merge multiple SARIF files into a single document."""
    runs = []

    for file_path in file_paths:
        if not file_path.exists():
            print(f"Warning: SARIF file not found: {file_path}")
            continue

        try:
            with open(file_path) as f:
                sarif_doc = json.load(f)

            # Extract runs from the document
            doc_runs = sarif_doc.get("runs", [])
            runs.extend(doc_runs)

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to read SARIF file {file_path}: {e}")
            continue

    if not runs:
        print("No valid SARIF files found to merge")
        return {}

    # Create merged document
    merged_run = create_merged_run(runs)

    merged_doc = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [merged_run]
    }

    # Write output if path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(merged_doc, f, indent=2)
        print(f"Merged SARIF document written to {output_path}")

    return merged_doc


def get_sarif_statistics(sarif_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Generate statistics about a SARIF document."""
    stats = {
        "total_runs": len(sarif_doc.get("runs", [])),
        "total_results": 0,
        "results_by_level": {},
        "results_by_tool": {},
        "unique_files": set(),
        "rule_count": 0
    }

    for run in sarif_doc.get("runs", []):
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "unknown")
        results = run.get("results", [])
        rules = run.get("tool", {}).get("driver", {}).get("rules", [])

        stats["total_results"] += len(results)
        stats["results_by_tool"][tool_name] = len(results)
        stats["rule_count"] += len(rules)

        for result in results:
            level = result.get("level", "unknown")
            stats["results_by_level"][level] = stats["results_by_level"].get(level, 0) + 1

            # Track unique files
            for location in result.get("locations", []):
                phys_loc = location.get("physicalLocation", {})
                uri = phys_loc.get("artifactLocation", {}).get("uri", "")
                if uri:
                    stats["unique_files"].add(uri)

    stats["unique_files"] = len(stats["unique_files"])
    return stats


def filter_sarif_by_severity(sarif_doc: Dict[str, Any], min_level: str = "warning") -> Dict[str, Any]:
    """Filter SARIF document to only include results at or above specified severity level."""
    level_order = {"error": 3, "warning": 2, "note": 1, "none": 0}
    min_level_value = level_order.get(min_level.lower(), 2)

    filtered_doc = {
        "version": sarif_doc.get("version", "2.1.0"),
        "$schema": sarif_doc.get("$schema", ""),
        "runs": []
    }

    for run in sarif_doc.get("runs", []):
        filtered_results = []

        for result in run.get("results", []):
            result_level = result.get("level", "warning")
            result_level_value = level_order.get(result_level.lower(), 2)

            if result_level_value >= min_level_value:
                filtered_results.append(result)

        if filtered_results:
            filtered_run = run.copy()
            filtered_run["results"] = filtered_results
            filtered_doc["runs"].append(filtered_run)

    return filtered_doc


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: sarif_merge.py <output_path> <sarif_file1> [sarif_file2] ...")
        print("       sarif_merge.py --stats <sarif_file>")
        print("       sarif_merge.py --filter <min_level> <input_file> <output_file>")
        sys.exit(1)

    if sys.argv[1] == "--stats":
        # Show statistics for a SARIF file
        sarif_file = Path(sys.argv[2])
        if not sarif_file.exists():
            print(f"Error: File not found: {sarif_file}")
            sys.exit(1)

        with open(sarif_file) as f:
            sarif_doc = json.load(f)

        stats = get_sarif_statistics(sarif_doc)
        print(json.dumps(stats, indent=2))

    elif sys.argv[1] == "--filter":
        # Filter SARIF file by severity level
        if len(sys.argv) < 5:
            print("Usage: sarif_merge.py --filter <min_level> <input_file> <output_file>")
            sys.exit(1)

        min_level = sys.argv[2]
        input_file = Path(sys.argv[3])
        output_file = Path(sys.argv[4])

        if not input_file.exists():
            print(f"Error: Input file not found: {input_file}")
            sys.exit(1)

        with open(input_file) as f:
            sarif_doc = json.load(f)

        filtered_doc = filter_sarif_by_severity(sarif_doc, min_level)

        with open(output_file, 'w') as f:
            json.dump(filtered_doc, f, indent=2)

        print(f"Filtered SARIF document written to {output_file}")

    else:
        # Merge SARIF files
        output_path = Path(sys.argv[1])
        input_files = [Path(p) for p in sys.argv[2:]]

        merged_doc = merge_sarif_files(*input_files, output_path=output_path)

        if merged_doc:
            stats = get_sarif_statistics(merged_doc)
            print(f"Merge completed: {stats['total_results']} results from {stats['total_runs']} runs")