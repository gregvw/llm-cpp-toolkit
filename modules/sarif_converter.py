#!/usr/bin/env python3
"""SARIF (Static Analysis Results Interchange Format) converter for llmtk.

Converts analysis reports from clang-tidy, cppcheck, and IWYU to SARIF format.
Provides merge functionality to combine multiple tools into a single SARIF report.
"""

import json
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
from urllib.request import pathname2url


def create_sarif_run(tool_name: str, tool_version: str = "unknown", rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Create a SARIF run structure for a tool."""
    return {
        "tool": {
            "driver": {
                "name": tool_name,
                "version": tool_version,
                "informationUri": f"https://github.com/llvm/{tool_name}" if tool_name.startswith("clang") else None,
                "rules": rules or []
            }
        },
        "results": [],
        "artifacts": [],
        "invocations": [{
            "executionSuccessful": True,
            "startTimeUtc": datetime.utcnow().isoformat() + "Z"
        }]
    }


def create_sarif_result(
    rule_id: str,
    message: str,
    level: str,
    file_path: str,
    line: int,
    column: int,
    end_line: Optional[int] = None,
    end_column: Optional[int] = None,
    fixes: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Create a SARIF result (finding) structure."""
    location = {
        "physicalLocation": {
            "artifactLocation": {
                "uri": pathname2url(file_path),
                "uriBaseId": "%SRCROOT%"
            },
            "region": {
                "startLine": line,
                "startColumn": column
            }
        }
    }

    if end_line is not None:
        location["physicalLocation"]["region"]["endLine"] = end_line
    if end_column is not None:
        location["physicalLocation"]["region"]["endColumn"] = end_column

    result = {
        "ruleId": rule_id,
        "message": {"text": message},
        "level": level,
        "locations": [location]
    }

    if fixes:
        result["fixes"] = fixes

    return result


def map_severity_to_sarif_level(severity: str) -> str:
    """Map tool-specific severity to SARIF level."""
    severity_lower = severity.lower()
    if severity_lower in ["error", "fatal error", "fatal"]:
        return "error"
    elif severity_lower in ["warning", "warn"]:
        return "warning"
    elif severity_lower in ["note", "info", "information"]:
        return "note"
    elif severity_lower in ["remark", "style"]:
        return "note"
    else:
        return "warning"  # Default fallback


def convert_clang_tidy_to_sarif(clang_tidy_report: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    """Convert clang-tidy JSON report to SARIF format."""
    tool_version = "unknown"
    if clang_tidy_report.get("meta", {}).get("version"):
        tool_version = clang_tidy_report["meta"]["version"]

    # Extract rules from diagnostics
    rules = {}
    for diag in clang_tidy_report.get("diagnostics", []):
        rule_id = diag.get("check", "clang-tidy")
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": f"clang-tidy check: {rule_id}"},
                "fullDescription": {"text": f"Issue detected by clang-tidy check {rule_id}"},
                "helpUri": f"https://clang.llvm.org/extra/clang-tidy/checks/{rule_id.replace('-', '_')}.html"
            }

    run = create_sarif_run("clang-tidy", tool_version, list(rules.values()))

    # Convert diagnostics to results
    for diag in clang_tidy_report.get("diagnostics", []):
        rule_id = diag.get("check", "clang-tidy")
        level = map_severity_to_sarif_level(diag.get("severity", "warning"))

        # Convert fixes if available
        fixes = []
        for fix in clang_tidy_report.get("fixes", []):
            if fix.get("file") == diag.get("file"):
                replacements = []
                for repl in fix.get("replacements", []):
                    replacements.append({
                        "deletedRegion": {
                            "startLine": 1,  # Will need to calculate from offset
                            "startColumn": 1,
                            "byteOffset": repl.get("offset", 0),
                            "byteLength": repl.get("length", 0)
                        },
                        "insertedContent": {"text": repl.get("replacement", "")}
                    })
                if replacements:
                    fixes.append({
                        "description": {"text": f"Fix suggested by clang-tidy"},
                        "artifactChanges": [{
                            "artifactLocation": {
                                "uri": pathname2url(diag.get("file", "")),
                                "uriBaseId": "%SRCROOT%"
                            },
                            "replacements": replacements
                        }]
                    })

        result = create_sarif_result(
            rule_id=rule_id,
            message=diag.get("message", ""),
            level=level,
            file_path=diag.get("file", ""),
            line=diag.get("line", 1),
            column=diag.get("column", 1),
            fixes=fixes if fixes else None
        )
        run["results"].append(result)

    return run


def convert_cppcheck_to_sarif(cppcheck_report: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    """Convert cppcheck JSON report to SARIF format."""
    tool_version = "unknown"
    if cppcheck_report.get("meta", {}).get("version"):
        tool_version = cppcheck_report["meta"]["version"]

    # Extract rules from issues
    rules = {}
    for issue in cppcheck_report.get("issues", []):
        rule_id = issue.get("id", "cppcheck")
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": f"cppcheck check: {rule_id}"},
                "fullDescription": {"text": issue.get("verbose", issue.get("message", ""))},
                "helpUri": f"https://cppcheck.sourceforge.io/"
            }

    run = create_sarif_run("cppcheck", tool_version, list(rules.values()))

    # Convert issues to results
    for issue in cppcheck_report.get("issues", []):
        rule_id = issue.get("id", "cppcheck")
        level = map_severity_to_sarif_level(issue.get("severity", "warning"))

        # Handle multiple locations
        locations = issue.get("locations", [])
        if locations:
            primary_loc = locations[0]
            result = create_sarif_result(
                rule_id=rule_id,
                message=issue.get("message", ""),
                level=level,
                file_path=primary_loc.get("file", ""),
                line=primary_loc.get("line", 1),
                column=primary_loc.get("column", 1)
            )

            # Add secondary locations if any
            if len(locations) > 1:
                result["relatedLocations"] = []
                for loc in locations[1:]:
                    result["relatedLocations"].append({
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": pathname2url(loc.get("file", "")),
                                "uriBaseId": "%SRCROOT%"
                            },
                            "region": {
                                "startLine": loc.get("line", 1),
                                "startColumn": loc.get("column", 1)
                            }
                        },
                        "message": {"text": "Related location"}
                    })

            run["results"].append(result)

    return run


def convert_iwyu_to_sarif(iwyu_report: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    """Convert IWYU JSON report to SARIF format."""
    tool_version = "unknown"
    if iwyu_report.get("meta", {}).get("version"):
        tool_version = iwyu_report["meta"]["version"]

    rules = {
        "include-what-you-use": {
            "id": "include-what-you-use",
            "shortDescription": {"text": "Include What You Use analysis"},
            "fullDescription": {"text": "Suggests changes to #include directives"},
            "helpUri": "https://include-what-you-use.org/"
        }
    }

    run = create_sarif_run("include-what-you-use", tool_version, list(rules.values()))

    # Convert issues to results
    for issue in iwyu_report.get("issues", []):
        file_path = issue.get("file", "")

        # Create results for additions
        for add_item in issue.get("suggest_add", []):
            result = create_sarif_result(
                rule_id="include-what-you-use",
                message=f"Add include: {add_item}",
                level="note",
                file_path=file_path,
                line=1,  # IWYU doesn't provide specific line numbers for additions
                column=1
            )
            run["results"].append(result)

        # Create results for removals
        for remove_item in issue.get("suggest_remove", []):
            result = create_sarif_result(
                rule_id="include-what-you-use",
                message=f"Remove include: {remove_item}",
                level="note",
                file_path=file_path,
                line=1,  # IWYU doesn't provide specific line numbers for removals
                column=1
            )
            run["results"].append(result)

    return run


def merge_sarif_runs(*runs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple SARIF runs into a single SARIF document."""
    sarif_doc = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": list(runs)
    }
    return sarif_doc


def write_sarif_report(sarif_doc: Dict[str, Any], output_path: Path) -> None:
    """Write SARIF document to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(sarif_doc, f, indent=2)


def convert_reports_to_sarif(
    clang_tidy_path: Optional[Path] = None,
    cppcheck_path: Optional[Path] = None,
    iwyu_path: Optional[Path] = None,
    output_path: Path = Path("exports/reports/analysis.sarif"),
    project_root: Path = Path(".")
) -> bool:
    """Convert analysis reports to SARIF format and merge them."""
    runs = []

    if clang_tidy_path and clang_tidy_path.exists():
        try:
            with open(clang_tidy_path) as f:
                clang_tidy_report = json.load(f)
            runs.append(convert_clang_tidy_to_sarif(clang_tidy_report, project_root))
        except Exception as e:
            print(f"Warning: Failed to convert clang-tidy report: {e}")

    if cppcheck_path and cppcheck_path.exists():
        try:
            with open(cppcheck_path) as f:
                cppcheck_report = json.load(f)
            runs.append(convert_cppcheck_to_sarif(cppcheck_report, project_root))
        except Exception as e:
            print(f"Warning: Failed to convert cppcheck report: {e}")

    if iwyu_path and iwyu_path.exists():
        try:
            with open(iwyu_path) as f:
                iwyu_report = json.load(f)
            runs.append(convert_iwyu_to_sarif(iwyu_report, project_root))
        except Exception as e:
            print(f"Warning: Failed to convert IWYU report: {e}")

    if not runs:
        print("No valid reports found to convert to SARIF")
        return False

    sarif_doc = merge_sarif_runs(*runs)
    write_sarif_report(sarif_doc, output_path)
    print(f"SARIF report written to {output_path}")
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: sarif_converter.py <output_path> [clang_tidy_path] [cppcheck_path] [iwyu_path]")
        sys.exit(1)

    output_path = Path(sys.argv[1])
    clang_tidy_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    cppcheck_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    iwyu_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None

    success = convert_reports_to_sarif(
        clang_tidy_path=clang_tidy_path,
        cppcheck_path=cppcheck_path,
        iwyu_path=iwyu_path,
        output_path=output_path
    )

    sys.exit(0 if success else 1)