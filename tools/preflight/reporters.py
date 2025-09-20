"""
Output formatting and reporting for llmtk preflight

Handles JSON, SARIF, and human-readable output formats with unified reporting.
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, TextIO, Set, Tuple
import pathlib


class Finding:
    """Represents a single preflight finding with enhanced metadata."""

    def __init__(
        self,
        file: str,
        line: int,
        col: int,
        rule: str,
        symbol: str,
        message: str,
        severity: str = "error",
        near: str = "",
        source: str = "preflight"
    ):
        self.file = file
        self.line = line
        self.col = col
        self.rule = rule
        self.symbol = symbol
        self.message = message
        self.severity = severity.lower()  # Normalize severity
        self.near = near
        self.source = source  # Which checker produced this finding

    def __eq__(self, other) -> bool:
        """Check equality for deduplication."""
        if not isinstance(other, Finding):
            return False
        return (
            self.file == other.file and
            self.line == other.line and
            self.col == other.col and
            self.rule == other.rule and
            self.message == other.message
        )

    def __hash__(self) -> int:
        """Hash for deduplication in sets."""
        return hash((self.file, self.line, self.col, self.rule, self.message))

    def __lt__(self, other) -> bool:
        """Sort ordering: by file, then line, then column, then severity."""
        if not isinstance(other, Finding):
            return NotImplemented

        # Primary sort: file path
        if self.file != other.file:
            return self.file < other.file

        # Secondary sort: line number
        if self.line != other.line:
            return self.line < other.line

        # Tertiary sort: column number
        if self.col != other.col:
            return self.col < other.col

        # Quaternary sort: severity (error < warning < info)
        severity_order = {"error": 0, "warning": 1, "info": 2}
        self_sev = severity_order.get(self.severity, 3)
        other_sev = severity_order.get(other.severity, 3)

        return self_sev < other_sev

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result = {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "rule": self.rule,
            "symbol": self.symbol,
            "message": self.message,
            "severity": self.severity,
            "source": self.source
        }
        if self.near:
            result["near"] = self.near
        return result

    def get_relative_file(self, base_path: Optional[pathlib.Path] = None) -> str:
        """Get file path relative to base_path for cleaner display."""
        if not base_path:
            base_path = pathlib.Path.cwd()

        try:
            file_path = pathlib.Path(self.file)
            if file_path.is_absolute():
                return str(file_path.relative_to(base_path))
        except (ValueError, OSError):
            pass

        return self.file

    def get_short_rule(self) -> str:
        """Get shortened rule name for display."""
        # Remove common prefixes for cleaner display
        rule = self.rule
        prefixes = ['json_', 'yaml_', 'toml_', 'shell_', 'cmake_', 'clang_', 'tree_sitter_']
        for prefix in prefixes:
            if rule.startswith(prefix):
                rule = rule[len(prefix):]
                break
        return rule


def deduplicate_findings(findings: List[Finding]) -> List[Finding]:
    """Remove duplicate findings while preserving order."""
    seen: Set[Finding] = set()
    deduplicated = []

    for finding in findings:
        if finding not in seen:
            seen.add(finding)
            deduplicated.append(finding)

    return deduplicated


def sort_findings(findings: List[Finding]) -> List[Finding]:
    """Sort findings by file, line, column, and severity."""
    return sorted(findings)


def filter_findings_by_severity(findings: List[Finding], min_severity: str = "warning") -> List[Finding]:
    """Filter findings by minimum severity level."""
    severity_levels = {"error": 0, "warning": 1, "info": 2}
    min_level = severity_levels.get(min_severity.lower(), 1)

    filtered = []
    for finding in findings:
        finding_level = severity_levels.get(finding.severity, 3)
        if finding_level <= min_level:
            filtered.append(finding)

    return filtered


def aggregate_findings_by_file(findings: List[Finding]) -> Dict[str, List[Finding]]:
    """Group findings by file path."""
    by_file: Dict[str, List[Finding]] = {}
    for finding in findings:
        if finding.file not in by_file:
            by_file[finding.file] = []
        by_file[finding.file].append(finding)

    return by_file


def get_finding_stats(findings: List[Finding]) -> Dict[str, Any]:
    """Get summary statistics for findings."""
    stats = {
        "total": len(findings),
        "errors": 0,
        "warnings": 0,
        "info": 0,
        "by_rule": {},
        "by_source": {},
        "by_file": {}
    }

    for finding in findings:
        # Count by severity
        if finding.severity == "error":
            stats["errors"] += 1
        elif finding.severity == "warning":
            stats["warnings"] += 1
        elif finding.severity == "info":
            stats["info"] += 1

        # Count by rule
        rule = finding.rule
        stats["by_rule"][rule] = stats["by_rule"].get(rule, 0) + 1

        # Count by source
        source = finding.source
        stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

        # Count by file
        file_path = finding.file
        stats["by_file"][file_path] = stats["by_file"].get(file_path, 0) + 1

    return stats


def format_findings_json(findings: List[Finding], version: str = "1.0.0") -> Dict[str, Any]:
    """Format findings as JSON structure with enhanced statistics."""
    stats = get_finding_stats(findings)

    return {
        "tool": "llmtk-preflight",
        "version": version,
        "generated_at": datetime.now().isoformat(),
        "findings": [f.to_dict() for f in findings],
        "summary": {
            "total": stats["total"],
            "errors": stats["errors"],
            "warnings": stats["warnings"],
            "info": stats["info"],
            "by_rule": stats["by_rule"],
            "by_source": stats["by_source"],
            "files_checked": len(stats["by_file"])
        }
    }


def format_findings_sarif(findings: List[Finding], version: str = "1.0.0") -> Dict[str, Any]:
    """Format findings as SARIF 2.1.0 structure with enhanced rule descriptions."""
    rules = {}
    results = []

    # Rule description mappings for better SARIF output
    rule_descriptions = {
        "json_syntax": {
            "name": "JSON Syntax Error",
            "short": "Invalid JSON syntax",
            "full": "Detects syntax errors in JSON files using Python's json module"
        },
        "yaml_syntax": {
            "name": "YAML Syntax Error",
            "short": "Invalid YAML syntax",
            "full": "Detects syntax errors in YAML files using PyYAML parser"
        },
        "toml_syntax": {
            "name": "TOML Syntax Error",
            "short": "Invalid TOML syntax",
            "full": "Detects syntax errors in TOML files using Python's tomllib/tomli"
        },
        "shell_syntax": {
            "name": "Shell Syntax Error",
            "short": "Invalid shell script syntax",
            "full": "Detects syntax errors in shell scripts using bash -n validation"
        },
        "cmake_syntax": {
            "name": "CMake Syntax Error",
            "short": "Invalid CMake syntax",
            "full": "Detects syntax errors in CMake files using cmake parser"
        },
        "clang_syntax": {
            "name": "C/C++ Syntax Error",
            "short": "Invalid C/C++ syntax",
            "full": "Detects syntax errors in C/C++ files using clang compiler"
        },
        "unclosed_delimiter": {
            "name": "Unclosed Delimiter",
            "short": "Missing closing delimiter",
            "full": "Detects unmatched opening delimiters (parentheses, brackets, braces)"
        },
        "unbalanced_delimiter": {
            "name": "Unbalanced Delimiter",
            "short": "Mismatched delimiters",
            "full": "Detects mismatched or unbalanced delimiter pairs"
        },
        "unclosed_quote": {
            "name": "Unclosed Quote",
            "short": "Missing closing quote",
            "full": "Detects unclosed string literals with missing closing quotes"
        },
        "tree_sitter_error": {
            "name": "Parse Error",
            "short": "Tree-sitter parse error",
            "full": "Parse errors detected by Tree-sitter syntax analysis"
        }
    }

    for finding in findings:
        # Track unique rules with enhanced descriptions
        if finding.rule not in rules:
            rule_info = rule_descriptions.get(finding.rule, {
                "name": finding.rule.replace("_", " ").title(),
                "short": f"{finding.rule} check",
                "full": f"Checks for {finding.rule} issues"
            })

            rules[finding.rule] = {
                "id": finding.rule,
                "name": rule_info["name"],
                "shortDescription": {"text": rule_info["short"]},
                "fullDescription": {"text": rule_info["full"]},
                "defaultConfiguration": {
                    "level": "error" if "syntax" in finding.rule or "error" in finding.rule else "warning"
                },
                "properties": {
                    "category": _get_rule_category(finding.rule),
                    "tags": _get_rule_tags(finding.rule)
                }
            }

        # Convert severity with support for info level
        if finding.severity == "error":
            sarif_level = "error"
        elif finding.severity == "warning":
            sarif_level = "warning"
        elif finding.severity == "info":
            sarif_level = "note"
        else:
            sarif_level = "warning"

        result = {
            "ruleId": finding.rule,
            "level": sarif_level,
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": _normalize_file_uri(finding.file)
                        },
                        "region": {
                            "startLine": finding.line,
                            "startColumn": finding.col
                        }
                    }
                }
            ],
            "properties": {
                "source": finding.source,
                "rule_category": _get_rule_category(finding.rule)
            }
        }

        if finding.near:
            result["locations"][0]["physicalLocation"]["region"]["snippet"] = {
                "text": finding.near
            }

        if finding.symbol:
            result["properties"]["symbol"] = finding.symbol

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
                        "semanticVersion": version,
                        "rules": list(rules.values())
                    }
                },
                "results": results,
                "properties": {
                    "summary": get_finding_stats(findings)
                }
            }
        ]
    }


def _get_rule_category(rule: str) -> str:
    """Get category for a rule."""
    if any(x in rule for x in ["syntax", "parse", "error"]):
        return "syntax"
    elif any(x in rule for x in ["delimiter", "quote", "brace", "paren"]):
        return "structure"
    elif any(x in rule for x in ["format", "style"]):
        return "style"
    elif any(x in rule for x in ["shellcheck", "SC"]):
        return "quality"
    else:
        return "general"


def _get_rule_tags(rule: str) -> List[str]:
    """Get tags for a rule."""
    tags = []

    if "json" in rule:
        tags.extend(["json", "syntax"])
    elif "yaml" in rule:
        tags.extend(["yaml", "syntax"])
    elif "toml" in rule:
        tags.extend(["toml", "syntax"])
    elif "shell" in rule:
        tags.extend(["shell", "bash"])
    elif "cmake" in rule:
        tags.extend(["cmake", "build"])
    elif "clang" in rule:
        tags.extend(["cpp", "c", "compiler"])

    if "syntax" in rule:
        tags.append("syntax")
    if "delimiter" in rule or "quote" in rule:
        tags.append("structure")
    if "tree_sitter" in rule:
        tags.append("parser")

    return list(set(tags))  # Remove duplicates


def _normalize_file_uri(file_path: str) -> str:
    """Normalize file path to URI format for SARIF."""
    import os
    from urllib.parse import quote

    # Convert to absolute path if relative
    abs_path = os.path.abspath(file_path)

    # Convert to URI format
    if os.name == 'nt':  # Windows
        # Convert Windows path to URI
        abs_path = abs_path.replace('\\', '/')
        if abs_path.startswith('/'):
            return f"file://{abs_path}"
        else:
            return f"file:///{abs_path}"
    else:  # Unix-like
        return f"file://{abs_path}"


def format_findings_human(findings: List[Finding], use_table: bool = True, base_path: Optional[pathlib.Path] = None) -> str:
    """Format findings for human-readable output."""
    if not findings:
        return "✓ No issues found\n"

    if use_table:
        return _format_findings_table(findings, base_path)
    else:
        return _format_findings_detailed(findings, base_path)


def _format_findings_table(findings: List[Finding], base_path: Optional[pathlib.Path] = None) -> str:
    """Format findings as a clean table using tabulate-like formatting."""
    lines = []

    # Try to import tabulate, fall back to manual formatting
    try:
        from tabulate import tabulate
        use_tabulate = True
    except ImportError:
        use_tabulate = False

    # Prepare table data
    headers = ["File", "Line:Col", "Severity", "Rule", "Message"]
    table_data = []

    for finding in findings:
        file_display = finding.get_relative_file(base_path)
        if len(file_display) > 40:  # Truncate long file paths
            file_display = "..." + file_display[-37:]

        location = f"{finding.line}:{finding.col}"
        severity_display = "✗ ERR" if finding.severity == "error" else "⚠ WARN" if finding.severity == "warning" else "ℹ INFO"
        rule_display = finding.get_short_rule()

        message = finding.message
        if len(message) > 60:  # Truncate long messages
            message = message[:57] + "..."

        table_data.append([file_display, location, severity_display, rule_display, message])

    if use_tabulate:
        table_str = tabulate(table_data, headers=headers, tablefmt="simple", maxcolwidths=[40, 10, 8, 20, 60])
        lines.append("Preflight Issues Found:")
        lines.append("")
        lines.append(table_str)
    else:
        # Manual table formatting fallback
        lines.append("Preflight Issues Found:")
        lines.append("=" * 120)
        lines.append(f"{'File':<40} {'Line:Col':<10} {'Severity':<8} {'Rule':<20} Message")
        lines.append("-" * 120)

        for row in table_data:
            lines.append(f"{row[0]:<40} {row[1]:<10} {row[2]:<8} {row[3]:<20} {row[4]}")

    # Add summary
    stats = get_finding_stats(findings)
    lines.append("")
    lines.append("=" * 60)

    summary_parts = []
    if stats["errors"] > 0:
        summary_parts.append(f"{stats['errors']} errors")
    if stats["warnings"] > 0:
        summary_parts.append(f"{stats['warnings']} warnings")
    if stats["info"] > 0:
        summary_parts.append(f"{stats['info']} info")

    summary = f"Total: {stats['total']} issues ({', '.join(summary_parts)})"
    lines.append(summary)

    return "\n".join(lines) + "\n"


def _format_findings_detailed(findings: List[Finding], base_path: Optional[pathlib.Path] = None) -> str:
    """Format findings in detailed group-by-file format."""
    lines = []
    lines.append("Preflight Issues Found:")
    lines.append("=" * 50)

    # Group by file
    by_file = aggregate_findings_by_file(findings)

    for file_path, file_findings in by_file.items():
        display_path = file_findings[0].get_relative_file(base_path) if file_findings else file_path
        lines.append(f"\n{display_path}:")

        for finding in sorted(file_findings):
            severity_marker = "✗" if finding.severity == "error" else "⚠" if finding.severity == "warning" else "ℹ"
            location = f"{finding.line}:{finding.col}"
            rule_display = f"[{finding.get_short_rule()}]" if finding.rule else ""
            lines.append(f"  {severity_marker} {location:>8} {finding.message} {rule_display}")
            if finding.near:
                lines.append(f"             Near: {finding.near}")

    # Summary
    stats = get_finding_stats(findings)
    lines.append("\n" + "=" * 50)

    summary_parts = []
    if stats["errors"] > 0:
        summary_parts.append(f"{stats['errors']} errors")
    if stats["warnings"] > 0:
        summary_parts.append(f"{stats['warnings']} warnings")
    if stats["info"] > 0:
        summary_parts.append(f"{stats['info']} info")

    summary = f"Total: {stats['total']} issues ({', '.join(summary_parts)})"
    lines.append(summary)

    return "\n".join(lines) + "\n"


def output_json(findings: List[Finding], output_path: Optional[pathlib.Path] = None, version: str = "1.0.0") -> None:
    """Output findings as JSON to file or stdout."""
    # Process findings: deduplicate and sort
    processed_findings = sort_findings(deduplicate_findings(findings))
    data = format_findings_json(processed_findings, version)
    json_str = json.dumps(data, indent=2)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str)
    else:
        print(json_str)


def output_sarif(findings: List[Finding], output_path: pathlib.Path, version: str = "1.0.0") -> None:
    """Output findings as SARIF to file."""
    # Process findings: deduplicate and sort
    processed_findings = sort_findings(deduplicate_findings(findings))
    data = format_findings_sarif(processed_findings, version)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))


def output_human(findings: List[Finding], output_file: Optional[TextIO] = None, use_table: bool = True, base_path: Optional[pathlib.Path] = None) -> None:
    """Output findings in human-readable format."""
    # Process findings: deduplicate, sort, and format
    processed_findings = sort_findings(deduplicate_findings(findings))
    formatted = format_findings_human(processed_findings, use_table=use_table, base_path=base_path)

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