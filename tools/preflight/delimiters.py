"""
Delimiter and quote checking for llmtk preflight

Implements Tree-sitter-based and fallback stack checking for balanced
delimiters and quotes.
"""

import pathlib
from typing import List, Set, Optional, Tuple, Iterator
from .reporters import Finding


# Try to import tree-sitter, fall back to manual parsing if not available
try:
    import tree_sitter
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class DelimiterChecker:
    """Base class for delimiter checking."""

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        """Check a file for delimiter issues."""
        raise NotImplementedError


class FallbackDelimiterChecker(DelimiterChecker):
    """Fallback delimiter checker using simple line-by-line parsing."""

    PAIRS = {'(': ')', '[': ']', '{': '}'}
    OPEN = set(PAIRS.keys())
    CLOSE = set(PAIRS.values())

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        """Check file using fallback line-by-line parser."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return [Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="file_read_error",
                symbol="",
                message=f"Could not read file: {file_path}",
                severity="error"
            )]

        findings = []
        findings.extend(self._check_delimiters(file_path, content))
        findings.extend(self._check_quotes(file_path, content))

        return findings

    def _check_delimiters(self, file_path: pathlib.Path, content: str) -> List[Finding]:
        """Check delimiter balance using stack-based approach."""
        findings = []
        stack = []  # Stack of (symbol, line, col)

        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            col = 0
            in_string = None  # Track if we're inside a string
            escaped = False

            while col < len(line):
                char = line[col]

                # Handle string literals to avoid false positives
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == '\\':
                        escaped = True
                    elif char == in_string:
                        in_string = None
                elif char in ('"', "'"):
                    in_string = char
                elif char in self.OPEN:
                    stack.append((char, line_num, col + 1))
                elif char in self.CLOSE:
                    if not stack:
                        findings.append(Finding(
                            file=str(file_path),
                            line=line_num,
                            col=col + 1,
                            rule="unbalanced_delimiter",
                            symbol=char,
                            message=f"Closing '{char}' without matching opener",
                            severity="error",
                            near=line[max(0, col-10):col+10].strip()
                        ))
                    else:
                        expected_close = self.PAIRS.get(stack[-1][0])
                        if expected_close != char:
                            findings.append(Finding(
                                file=str(file_path),
                                line=line_num,
                                col=col + 1,
                                rule="mismatched_delimiter",
                                symbol=char,
                                message=f"Expected '{expected_close}' but found '{char}'",
                                severity="error",
                                near=line[max(0, col-10):col+10].strip()
                            ))
                        stack.pop()

                col += 1

        # Report unclosed delimiters
        for symbol, line_num, col_num in stack:
            findings.append(Finding(
                file=str(file_path),
                line=line_num,
                col=col_num,
                rule="unclosed_delimiter",
                symbol=symbol,
                message=f"Unclosed '{symbol}' delimiter",
                severity="error"
            ))

        return findings

    def _check_quotes(self, file_path: pathlib.Path, content: str) -> List[Finding]:
        """Check quote balance and handle multi-line strings."""
        findings = []
        lines = content.splitlines()

        # Track state across lines for multi-line strings
        in_multiline_string = None
        multiline_start_line = 0

        for line_num, line in enumerate(lines, 1):
            col = 0
            while col < len(line):
                char = line[col]

                # Handle potential multi-line string markers (like triple quotes)
                if col + 2 < len(line) and line[col:col+3] in ('"""', "'''"):
                    triple_quote = line[col:col+3]
                    if in_multiline_string == triple_quote:
                        # End of multi-line string
                        in_multiline_string = None
                        col += 3
                        continue
                    elif not in_multiline_string:
                        # Start of multi-line string
                        in_multiline_string = triple_quote
                        multiline_start_line = line_num
                        col += 3
                        continue

                # Skip if we're inside a multi-line string
                if in_multiline_string:
                    col += 1
                    continue

                # Check for unmatched single quotes in this line
                if char in ('"', "'"):
                    quote_type = char
                    start_col = col
                    col += 1
                    escaped = False
                    found_end = False

                    while col < len(line):
                        if escaped:
                            escaped = False
                        elif line[col] == '\\':
                            escaped = True
                        elif line[col] == quote_type:
                            found_end = True
                            break
                        col += 1

                    if not found_end:
                        findings.append(Finding(
                            file=str(file_path),
                            line=line_num,
                            col=start_col + 1,
                            rule="unclosed_quote",
                            symbol=quote_type,
                            message=f"Unclosed {quote_type} quote",
                            severity="error",
                            near=line[max(0, start_col-5):start_col+15].strip()
                        ))
                    else:
                        col += 1  # Move past the closing quote
                else:
                    col += 1

        # Report unclosed multi-line strings
        if in_multiline_string:
            findings.append(Finding(
                file=str(file_path),
                line=multiline_start_line,
                col=1,
                rule="unclosed_multiline_string",
                symbol=in_multiline_string,
                message=f"Unclosed {in_multiline_string} multi-line string",
                severity="error"
            ))

        return findings


class TreeSitterDelimiterChecker(DelimiterChecker):
    """Tree-sitter based delimiter checker (when available)."""

    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise RuntimeError("Tree-sitter not available")
        # TODO: Initialize tree-sitter parsers for supported languages

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        """Check file using tree-sitter parser."""
        # TODO: Implement tree-sitter based checking
        # For now, fallback to manual parsing
        fallback = FallbackDelimiterChecker()
        return fallback.check_file(file_path)


def get_delimiter_checker() -> DelimiterChecker:
    """Get the best available delimiter checker."""
    if TREE_SITTER_AVAILABLE:
        try:
            return TreeSitterDelimiterChecker()
        except RuntimeError:
            pass

    return FallbackDelimiterChecker()


def check_markdown_fences(file_path: pathlib.Path, content: str) -> List[Finding]:
    """Check for balanced markdown code fences."""
    findings = []
    lines = content.splitlines()
    fence_stack = []  # Stack of (fence_type, line_num, language)

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Check for code fences (``` or ```)
        if stripped.startswith('```'):
            fence_info = stripped[3:].strip()
            if fence_stack and fence_stack[-1][0] == '```':
                # Closing fence
                fence_stack.pop()
            else:
                # Opening fence
                fence_stack.append(('```', line_num, fence_info))

    # Report unclosed fences
    for fence_type, line_num, language in fence_stack:
        lang_info = f" (lang={language})" if language else ""
        findings.append(Finding(
            file=str(file_path),
            line=line_num,
            col=1,
            rule="unclosed_code_fence",
            symbol=fence_type,
            message=f"Unclosed {fence_type} code fence{lang_info}",
            severity="error"
        ))

    return findings