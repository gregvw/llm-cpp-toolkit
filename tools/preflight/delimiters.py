"""
Delimiter and quote checking for llmtk preflight

Implements Tree-sitter-based and fallback stack checking for balanced
delimiters and quotes.
"""

import pathlib
from typing import Dict, List, Optional, Set, Tuple

from .reporters import Finding


# Try to import tree-sitter, fall back to manual parsing if not available
try:  # pragma: no cover - import availability depends on environment
    from tree_sitter import Parser  # type: ignore

    TREE_SITTER_AVAILABLE = True
except ImportError:  # pragma: no cover
    Parser = None  # type: ignore
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

    # Map file suffixes to tree-sitter language names
    LANGUAGE_BY_EXTENSION: Dict[str, str] = {
        # C / C++ family
        ".c": "c",
        ".h": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".c++": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        ".hh": "cpp",
        ".h++": "cpp",

        # Build / configuration
        ".cmake": "cmake",
        ".json": "json",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",

        # Documentation & scripts
        ".md": "markdown",
        ".markdown": "markdown",
        ".py": "python",
        ".sh": "bash",
        ".bash": "bash",
    }

    LANGUAGE_BY_FILENAME: Dict[str, str] = {
        "cmakelists.txt": "cmake",
    }

    _CLOSING_DELIMS: Set[str] = {"}", ")", "]"}
    _OPENING_DELIMS: Set[str] = {"{", "(", "["}

    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise RuntimeError("Tree-sitter not available")

        try:  # pragma: no cover - depends on optional package
            from tree_sitter_languages import get_language, get_parser  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("tree_sitter_languages package not available") from exc

        self._get_language = get_language
        self._get_parser = get_parser
        self._parser_cache: Dict[str, Parser] = {}
        self._fallback = FallbackDelimiterChecker()

    def _language_for_path(self, file_path: pathlib.Path) -> Optional[str]:
        """Return tree-sitter language key for a path, if supported."""
        name = file_path.name.lower()
        if name in self.LANGUAGE_BY_FILENAME:
            return self.LANGUAGE_BY_FILENAME[name]

        suffix = file_path.suffix.lower()
        return self.LANGUAGE_BY_EXTENSION.get(suffix)

    def _get_parser_for_language(self, language: str) -> Optional[Parser]:
        """Return cached parser for the language, if available."""
        if language in self._parser_cache:
            return self._parser_cache[language]

        parser: Optional[Parser] = None

        # Attempt to get a fully configured parser from helper first
        try:
            parser = self._get_parser(language)
        except Exception:
            parser = None

        if parser is None:
            try:
                language_obj = self._get_language(language)
            except Exception:
                return None

            parser = Parser()
            parser.set_language(language_obj)

        self._parser_cache[language] = parser
        return parser

    @staticmethod
    def _decode_bytes(data: bytes) -> str:
        return data.decode("utf-8", errors="replace")

    def _node_snippet(self, raw_bytes: bytes, lines: List[str], start_byte: int, end_byte: int, line_index: int) -> str:
        """Return a short snippet of source code around a node."""
        if end_byte > start_byte:
            snippet = self._decode_bytes(raw_bytes[start_byte:end_byte])
            snippet = snippet.replace("\n", " ")
        elif 0 <= line_index < len(lines):
            snippet = lines[line_index].strip()
        else:
            snippet = ""

        snippet = snippet.strip()
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        return snippet

    def _finding_from_missing(self, file_path: pathlib.Path, node, raw_bytes: bytes, lines: List[str]) -> Finding:
        line, col = node.start_point
        symbol = node.type
        line_text = self._node_snippet(raw_bytes, lines, node.start_byte, node.end_byte, line)

        if symbol in self._CLOSING_DELIMS:
            message = f"Missing closing '{symbol}' (detected by tree-sitter)"
            rule = "missing_delimiter"
        elif symbol in self._OPENING_DELIMS:
            message = f"Missing opening '{symbol}' (detected by tree-sitter)"
            rule = "missing_delimiter"
        else:
            message = f"Missing syntax element '{symbol}' (tree-sitter)"
            rule = "missing_syntax"

        return Finding(
            file=str(file_path),
            line=line + 1,
            col=col + 1,
            rule=rule,
            symbol=symbol,
            message=message,
            severity="error",
            near=line_text
        )

    def _finding_from_error(self, file_path: pathlib.Path, node, raw_bytes: bytes, lines: List[str]) -> Finding:
        line, col = node.start_point
        snippet = self._node_snippet(raw_bytes, lines, node.start_byte, node.end_byte, line)

        message = "Tree-sitter parse error"
        if snippet:
            message += f" near '{snippet}'"

        return Finding(
            file=str(file_path),
            line=line + 1,
            col=col + 1,
            rule="tree_sitter_error",
            symbol="ERROR",
            message=message,
            severity="error",
            near=snippet
        )

    def _collect_findings(self, file_path: pathlib.Path, tree, raw_bytes: bytes, lines: List[str]) -> List[Finding]:
        findings: List[Finding] = []
        seen: Set[Tuple[int, int, str]] = set()
        stack = [tree.root_node]

        while stack:
            node = stack.pop()

            if node.is_missing:
                key = (node.start_point[0], node.start_point[1], node.type)
                if key not in seen:
                    findings.append(self._finding_from_missing(file_path, node, raw_bytes, lines))
                    seen.add(key)

            elif node.type == "ERROR":
                key = (node.start_point[0], node.start_point[1], node.type)
                if key not in seen:
                    findings.append(self._finding_from_error(file_path, node, raw_bytes, lines))
                    seen.add(key)

            # Traverse children regardless so we collect nested errors/missing nodes
            stack.extend(list(getattr(node, "children", [])))

        return findings

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        """Check file using tree-sitter parser."""
        language_key = self._language_for_path(file_path)
        if not language_key:
            return self._fallback.check_file(file_path)

        parser = self._get_parser_for_language(language_key)
        if parser is None:
            return self._fallback.check_file(file_path)

        try:
            raw_bytes = file_path.read_bytes()
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

        text = self._decode_bytes(raw_bytes)
        lines = text.splitlines()

        try:
            tree = parser.parse(raw_bytes)
        except Exception:
            # If parsing fails unexpectedly, fall back to manual checks
            return self._fallback.check_file(file_path)

        if not tree.root_node.has_error:
            return []

        findings = self._collect_findings(file_path, tree, raw_bytes, lines)

        # Tree-sitter occasionally marks has_error without explicit ERROR nodes; ensure fallback covers
        if not findings:
            return self._fallback.check_file(file_path)

        return findings


def get_delimiter_checker() -> DelimiterChecker:
    """Get the best available delimiter checker."""
    if TREE_SITTER_AVAILABLE:
        try:
            return TreeSitterDelimiterChecker()
        except Exception:
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
