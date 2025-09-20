"""
Output formatting and reporting for llmtk preflight

Handles JSON, SARIF, and human-readable output formats.
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, TextIO
import pathlib


class Finding:
    """Represents a single preflight finding."""

    def __init__(
        self,
        file: str,
        line: int,
        col: int,
        rule: str,
        symbol: str,
        message: str,
        severity: str = "error",
        near: str = ""
    ):
        self.file = file
        self.line = line
        self.col = col
        self.rule = rule
        self.symbol = symbol
        self.message = message
        self.severity = severity
        self.near = near

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result = {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "rule": self.rule,
            "symbol": self.symbol,
            "message": self.message,
            "severity": self.severity
        }
        if self.near:
            result["near"] = self.near
        return result


def format_findings_json(findings: List[Finding], version: str = "1.0.0") -> Dict[str, Any]:
    """Format findings as JSON structure."""
    return {
        "tool": "llmtk-preflight",
        "version": version,
        "generated_at": datetime.now().isoformat(),
        "findings": [f.to_dict() for f in findings],
        "summary": {
            "total": len(findings),
            "errors": len([f for f in findings if f.severity == "error"]),
            "warnings": len([f for f in findings if f.severity == "warning"])
        }
    }


def format_findings_sarif(findings: List[Finding], version: str = "1.0.0") -> Dict[str, Any]:
    """Format findings as SARIF 2.1.0 structure."""
    rules = {}
    results = []

    for finding in findings:
        # Track unique rules
        if finding.rule not in rules:
            rules[finding.rule] = {
                "id": finding.rule,
                "name": finding.rule.replace("_", " ").title(),
                "shortDescription": {"text": f"{finding.rule} check"},
                "fullDescription": {"text": f"Checks for {finding.rule} issues"}
            }

        # Convert severity
        sarif_level = "error" if finding.severity == "error" else "warning"

        result = {
            "ruleId": finding.rule,
            "level": sarif_level,
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.file},
                        "region": {
                            "startLine": finding.line,
                            "startColumn": finding.col
                        }
                    }
                }
            ]
        }

        if finding.near:
            result["locations"][0]["physicalLocation"]["region"]["snippet"] = {
                "text": finding.near
            }

        results.append(result)

    return {
        "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "llmtk-preflight",
                        "version": version,
                        "informationUri": "https://github.com/gregvw/llm-cpp-toolkit",
                        "rules": list(rules.values())
                    }
                },
                "results": results
            }
        ]
    }


def format_findings_human(findings: List[Finding]) -> str:
    """Format findings for human-readable output."""
    if not findings:
        return "✓ No issues found\n"

    lines = []
    lines.append("Preflight Issues Found:")
    lines.append("=" * 50)

    # Group by file
    by_file: Dict[str, List[Finding]] = {}
    for finding in findings:
        if finding.file not in by_file:
            by_file[finding.file] = []
        by_file[finding.file].append(finding)

    for file_path, file_findings in by_file.items():
        lines.append(f"\n{file_path}:")
        for finding in file_findings:
            severity_marker = "✗" if finding.severity == "error" else "⚠"
            location = f"{finding.line}:{finding.col}"
            lines.append(f"  {severity_marker} {location:>8} {finding.message}")
            if finding.near:
                lines.append(f"             Near: {finding.near}")

    # Summary
    errors = len([f for f in findings if f.severity == "error"])
    warnings = len([f for f in findings if f.severity == "warning"])

    lines.append("\n" + "=" * 50)
    lines.append(f"Total: {len(findings)} issues ({errors} errors, {warnings} warnings)")

    return "\n".join(lines) + "\n"


def output_json(findings: List[Finding], output_path: Optional[pathlib.Path] = None, version: str = "1.0.0") -> None:
    """Output findings as JSON to file or stdout."""
    data = format_findings_json(findings, version)
    json_str = json.dumps(data, indent=2)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str)
    else:
        print(json_str)


def output_sarif(findings: List[Finding], output_path: pathlib.Path, version: str = "1.0.0") -> None:
    """Output findings as SARIF to file."""
    data = format_findings_sarif(findings, version)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))


def output_human(findings: List[Finding], output_file: Optional[TextIO] = None) -> None:
    """Output findings in human-readable format."""
    formatted = format_findings_human(findings)
    if output_file:
        output_file.write(formatted)
    else:
        print(formatted, end="")


def determine_exit_code(findings: List[Finding], strict: bool = False) -> int:
    """
    Determine appropriate exit code based on findings.

    Returns:
        0: No issues
        2: Warnings only (non-strict mode)
        3: Errors found
    """
    if not findings:
        return 0

    has_errors = any(f.severity == "error" for f in findings)
    has_warnings = any(f.severity == "warning" for f in findings)

    if has_errors:
        return 3
    elif has_warnings and strict:
        return 3
    elif has_warnings:
        return 2
    else:
        return 0