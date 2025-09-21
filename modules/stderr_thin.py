#!/usr/bin/env python3
"""
stderr-thin: Collapse compiler stderr into deterministic, budget-aware highlights.

This module processes compiler/linker diagnostics to:
1. Collapse duplicate template instantiation chains
2. Extract rule IDs and warning switches
3. Provide budget-aware context management
4. Output in both JSON and optional SARIF formats
"""

import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.request import pathname2url


@dataclass
class DiagnosticLocation:
    """Represents a source location in a diagnostic."""
    file: str
    line: int
    column: int

    def to_dict(self) -> Dict[str, Any]:
        return {"file": self.file, "line": self.line, "column": self.column}


@dataclass
class TemplateFrame:
    """Represents a frame in a template instantiation chain."""
    location: DiagnosticLocation
    template: str
    context: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "template": self.template,
            "context": self.context
        }


@dataclass
class DiagnosticRule:
    """Represents an extracted diagnostic rule."""
    rule_id: Optional[str]
    warning_flag: Optional[str]
    category: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "warning_flag": self.warning_flag,
            "category": self.category
        }


@dataclass
class ProcessedDiagnostic:
    """Represents a processed diagnostic with collapsed template chains."""
    severity: str
    message: str
    primary_location: DiagnosticLocation
    rule: DiagnosticRule
    template_trace: List[TemplateFrame]
    collapsed_frames: int
    fixit: Optional[str]
    raw_lines: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "message": self.message,
            "primary_location": self.primary_location.to_dict(),
            "rule": self.rule.to_dict(),
            "template_trace": [frame.to_dict() for frame in self.template_trace],
            "collapsed_frames": self.collapsed_frames,
            "fixit": self.fixit,
            "raw_line_count": len(self.raw_lines)
        }


class StderrThin:
    """Main class for processing stderr output."""

    # Regex patterns for parsing compiler diagnostics
    CLANG_DIAGNOSTIC_RE = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?P<severity>error|warning|note|remark|fatal error):\s*"
        r"(?P<message>.*?)(?:\s*\[(?P<flag>-W[^\]]+)\])?$"
    )

    GCC_DIAGNOSTIC_RE = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?P<severity>error|warning|note):\s*"
        r"(?P<message>.*?)$"
    )

    TEMPLATE_INSTANTIATION_RE = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?:note:\s*)?(?:required from|in instantiation of|instantiated from)\s*"
        r"(?P<context>.*?)$"
    )

    TEMPLATE_CONTEXT_RE = re.compile(
        r"template\s*<[^>]*>\s*(\w+(?:::\w+)*(?:<[^>]*>)?)"
    )

    def __init__(self, context_budget: int = 8000, level: str = "focused"):
        """Initialize stderr processor.

        Args:
            context_budget: Maximum characters in output
            level: Detail level (summary|focused|detailed)
        """
        self.context_budget = context_budget
        self.level = level
        self.diagnostics: List[ProcessedDiagnostic] = []
        self.counts = {"error": 0, "warning": 0, "note": 0, "remark": 0, "other": 0}

    def parse_stderr(self, stderr_text: str) -> None:
        """Parse stderr text and extract diagnostics."""
        lines = stderr_text.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Try to match a primary diagnostic
            match = self._match_diagnostic_line(line)
            if match:
                diagnostic, consumed_lines = self._parse_full_diagnostic(lines, i, match)
                if diagnostic:
                    self.diagnostics.append(diagnostic)
                    self.counts[diagnostic.severity] = self.counts.get(diagnostic.severity, 0) + 1
                i += consumed_lines
            else:
                i += 1

    def _match_diagnostic_line(self, line: str) -> Optional[re.Match]:
        """Try to match a diagnostic line with either Clang or GCC pattern."""
        match = self.CLANG_DIAGNOSTIC_RE.match(line)
        if match:
            return match
        return self.GCC_DIAGNOSTIC_RE.match(line)

    def _parse_full_diagnostic(self, lines: List[str], start_idx: int,
                             primary_match: re.Match) -> Tuple[Optional[ProcessedDiagnostic], int]:
        """Parse a full diagnostic including template instantiation chains."""
        raw_lines = [lines[start_idx]]
        consumed = 1

        # Extract primary location and rule
        primary_location = DiagnosticLocation(
            file=primary_match.group("file"),
            line=int(primary_match.group("line")),
            column=int(primary_match.group("column"))
        )

        severity = primary_match.group("severity")
        message = primary_match.group("message")
        warning_flag = primary_match.group("flag") if "flag" in primary_match.groupdict() else None

        # Extract rule ID from message or flag
        rule = self._extract_rule(message, warning_flag)

        # Parse template instantiation chain
        template_trace = []
        fixit = None

        # Look ahead for template instantiation notes and fix-its
        i = start_idx + 1
        while i < len(lines):
            line = lines[i].strip()

            # Check for template instantiation
            template_match = self.TEMPLATE_INSTANTIATION_RE.match(line)
            if template_match:
                frame = TemplateFrame(
                    location=DiagnosticLocation(
                        file=template_match.group("file"),
                        line=int(template_match.group("line")),
                        column=int(template_match.group("column"))
                    ),
                    template=self._extract_template_name(template_match.group("context")),
                    context=template_match.group("context")
                )
                template_trace.append(frame)
                raw_lines.append(line)
                consumed += 1
                i += 1
            # Check for fix-it suggestions
            elif "fix-it:" in line or "suggested replacement:" in line:
                fixit = line
                raw_lines.append(line)
                consumed += 1
                i += 1
            # Check if this line belongs to the diagnostic (indented or continuation)
            elif line.startswith("  ") or line.startswith("^") or line.startswith("~"):
                raw_lines.append(line)
                consumed += 1
                i += 1
            # Stop if we hit another diagnostic or empty line
            elif self._match_diagnostic_line(line) or not line:
                break
            else:
                i += 1

        # Collapse template trace if needed
        collapsed_trace, collapsed_count = self._collapse_template_trace(template_trace)

        diagnostic = ProcessedDiagnostic(
            severity=severity,
            message=message,
            primary_location=primary_location,
            rule=rule,
            template_trace=collapsed_trace,
            collapsed_frames=collapsed_count,
            fixit=fixit,
            raw_lines=raw_lines
        )

        return diagnostic, consumed

    def _extract_rule(self, message: str, warning_flag: Optional[str]) -> DiagnosticRule:
        """Extract rule information from diagnostic message and flags."""
        # Common Clang rule patterns
        rule_patterns = [
            r"\[([a-zA-Z-]+[a-zA-Z])\]",  # [clang-tidy-check]
            r"warning: ([a-zA-Z-]+)",      # warning: unused-variable
        ]

        rule_id = None
        for pattern in rule_patterns:
            match = re.search(pattern, message)
            if match:
                rule_id = match.group(1)
                break

        # Determine category
        category = "compilation"
        if warning_flag:
            category = "warning"
        elif "error" in message.lower():
            category = "error"
        elif "template" in message.lower():
            category = "template"
        elif "link" in message.lower():
            category = "linking"

        return DiagnosticRule(
            rule_id=rule_id,
            warning_flag=warning_flag,
            category=category
        )

    def _extract_template_name(self, context: str) -> str:
        """Extract template name from instantiation context."""
        match = self.TEMPLATE_CONTEXT_RE.search(context)
        if match:
            return match.group(1)

        # Fallback: try to extract any identifier that looks like a template
        words = context.split()
        for word in words:
            if "<" in word and ">" in word:
                return word

        return context[:50]  # Fallback to first 50 chars

    def _collapse_template_trace(self, trace: List[TemplateFrame]) -> Tuple[List[TemplateFrame], int]:
        """Collapse duplicate template instantiation chains."""
        if len(trace) <= 3:
            return trace, 0

        # Keep first and last frames, collapse middle if there are duplicates
        collapsed = [trace[0]]
        collapsed_count = 0

        # Look for repeating patterns in the middle
        middle_frames = trace[1:-1]
        if len(middle_frames) > 2:
            # Simple deduplication: if we see the same template name repeatedly,
            # keep only the first and last occurrence
            seen_templates = {}
            for i, frame in enumerate(middle_frames):
                if frame.template in seen_templates:
                    collapsed_count += 1
                else:
                    seen_templates[frame.template] = i
                    collapsed.append(frame)
        else:
            collapsed.extend(middle_frames)

        # Always keep the last frame
        if len(trace) > 1:
            collapsed.append(trace[-1])

        return collapsed, collapsed_count

    def get_budget_aware_output(self) -> List[ProcessedDiagnostic]:
        """Return diagnostics that fit within the context budget."""
        if self.level == "summary":
            # Only errors and warnings
            filtered = [d for d in self.diagnostics if d.severity in ["error", "warning"]]
        elif self.level == "focused":
            # Errors, warnings, and important notes
            filtered = [d for d in self.diagnostics if d.severity in ["error", "warning", "note"]]
        else:  # detailed
            filtered = self.diagnostics

        # Sort by severity (errors first)
        severity_order = {"error": 0, "fatal error": 0, "warning": 1, "note": 2, "remark": 3}
        filtered.sort(key=lambda d: severity_order.get(d.severity, 4))

        # Apply budget constraints
        current_size = 0
        result = []

        for diagnostic in filtered:
            # Estimate size (rough approximation)
            diag_size = len(diagnostic.message) + len(str(diagnostic.primary_location.to_dict()))
            diag_size += sum(len(str(frame.to_dict())) for frame in diagnostic.template_trace)

            if current_size + diag_size <= self.context_budget:
                result.append(diagnostic)
                current_size += diag_size
            else:
                break

        return result

    def to_json(self) -> Dict[str, Any]:
        """Export diagnostics as JSON."""
        diagnostics = self.get_budget_aware_output()

        return {
            "_meta": {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "level": self.level,
                "context_budget": self.context_budget,
                "structured_source": "stderr-thin"
            },
            "counts": self.counts,
            "view": {
                "level": self.level,
                "context_budget": self.context_budget,
                "context_used": sum(len(json.dumps(d.to_dict())) for d in diagnostics),
                "context_full": sum(len(json.dumps(d.to_dict())) for d in self.diagnostics),
                "context_truncated": len(self.diagnostics) - len(diagnostics)
            },
            "diagnostics": [d.to_dict() for d in diagnostics],
            "highlights": self._generate_highlights(diagnostics)
        }

    def to_sarif(self) -> Dict[str, Any]:
        """Export diagnostics as SARIF format."""
        diagnostics = self.get_budget_aware_output()

        # Create SARIF structure
        sarif_results = []
        for diag in diagnostics:
            # Map severity to SARIF level
            level_map = {
                "error": "error",
                "fatal error": "error",
                "warning": "warning",
                "note": "note",
                "remark": "note"
            }
            level = level_map.get(diag.severity, "warning")

            result = {
                "ruleId": diag.rule.rule_id or "compiler-diagnostic",
                "message": {"text": diag.message},
                "level": level,
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": pathname2url(diag.primary_location.file),
                            "uriBaseId": "%SRCROOT%"
                        },
                        "region": {
                            "startLine": diag.primary_location.line,
                            "startColumn": diag.primary_location.column
                        }
                    }
                }]
            }

            # Add template trace as related locations
            if diag.template_trace:
                result["relatedLocations"] = []
                for frame in diag.template_trace:
                    result["relatedLocations"].append({
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": pathname2url(frame.location.file),
                                "uriBaseId": "%SRCROOT%"
                            },
                            "region": {
                                "startLine": frame.location.line,
                                "startColumn": frame.location.column
                            }
                        },
                        "message": {"text": f"Template instantiation: {frame.context}"}
                    })

            # Add fix-it if available
            if diag.fixit:
                result["fixes"] = [{
                    "description": {"text": "Compiler suggested fix"},
                    "artifactChanges": [{
                        "artifactLocation": {
                            "uri": pathname2url(diag.primary_location.file),
                            "uriBaseId": "%SRCROOT%"
                        },
                        "replacements": [{
                            "deletedRegion": {
                                "startLine": diag.primary_location.line,
                                "startColumn": diag.primary_location.column
                            },
                            "insertedContent": {"text": diag.fixit}
                        }]
                    }]
                }]

            sarif_results.append(result)

        # Create rules from diagnostics
        rules = []
        seen_rules = set()
        for diag in diagnostics:
            rule_id = diag.rule.rule_id or "compiler-diagnostic"
            if rule_id not in seen_rules:
                seen_rules.add(rule_id)
                rules.append({
                    "id": rule_id,
                    "shortDescription": {"text": f"Compiler diagnostic: {rule_id}"},
                    "fullDescription": {"text": f"Diagnostic from {diag.rule.category}"},
                    "properties": {
                        "category": diag.rule.category,
                        "tags": ["compiler"]
                    }
                })

        return {
            "version": "2.1.0",
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "stderr-thin",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/gregvw/llm-cpp-toolkit",
                        "rules": rules
                    }
                },
                "results": sarif_results,
                "invocations": [{
                    "executionSuccessful": True,
                    "startTimeUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }]
            }]
        }

    def _generate_highlights(self, diagnostics: List[ProcessedDiagnostic]) -> List[str]:
        """Generate human-readable highlights."""
        highlights = []

        for diag in diagnostics:
            highlight = f"{diag.severity}: {diag.message}"
            if diag.rule.warning_flag:
                highlight += f" [{diag.rule.warning_flag}]"

            location = f"{diag.primary_location.file}:{diag.primary_location.line}:{diag.primary_location.column}"
            highlight = f"{location}: {highlight}"

            if diag.collapsed_frames > 0:
                highlight += f" (collapsed {diag.collapsed_frames} template frames)"

            highlights.append(highlight)

        return highlights


def main():
    """CLI entry point for stderr-thin."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Collapse compiler stderr into budget-aware highlights")
    parser.add_argument("--log", help="Path to stderr log file to process")
    parser.add_argument("--compile", help="Substring filter for compile_commands.json entries")
    parser.add_argument("--compile-index", type=int, help="Explicit index into compile_commands.json")
    parser.add_argument("--level", choices=["summary", "focused", "detailed"],
                       default="focused", help="Detail level")
    parser.add_argument("--context-budget", type=int, default=8000,
                       help="Maximum characters in output")
    parser.add_argument("--sarif", help="Output SARIF file path")
    parser.add_argument("--json", help="Output JSON file path")
    parser.add_argument("--text", help="Output text file path")

    args = parser.parse_args()

    # Read input
    if args.log:
        try:
            with open(args.log, 'r') as f:
                stderr_text = f.read()
        except FileNotFoundError:
            print(f"Error: Log file not found: {args.log}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        stderr_text = sys.stdin.read()

    # Process stderr
    processor = StderrThin(context_budget=args.context_budget, level=args.level)
    processor.parse_stderr(stderr_text)

    # Create output directory
    output_dir = Path("exports/diagnostics")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate outputs
    json_output = processor.to_json()

    # Write JSON output
    json_path = Path(args.json) if args.json else output_dir / "stderr-thin.json"
    with open(json_path, 'w') as f:
        json.dump(json_output, f, indent=2)

    # Write SARIF output if requested
    if args.sarif:
        sarif_output = processor.to_sarif()
        sarif_path = Path(args.sarif)
        with open(sarif_path, 'w') as f:
            json.dump(sarif_output, f, indent=2)

    # Write text output
    text_path = Path(args.text) if args.text else output_dir / "stderr-thin.txt"
    with open(text_path, 'w') as f:
        f.write("\n".join(json_output["highlights"]))

    # Write raw stderr
    raw_path = output_dir / "stderr-raw.txt"
    with open(raw_path, 'w') as f:
        f.write(stderr_text)

    print(f"Processed {len(processor.diagnostics)} diagnostics")
    print(f"JSON output: {json_path}")
    if args.sarif:
        print(f"SARIF output: {args.sarif}")
    print(f"Text output: {text_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())