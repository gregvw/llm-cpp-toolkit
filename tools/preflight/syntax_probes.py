"""
External syntax checking probes for llmtk preflight

Implements fast syntax checking using external tools like clang, jq, etc.
"""

import pathlib
import subprocess
import shutil
from typing import List, Optional, Dict, Any
from .reporters import Finding


class SyntaxProbe:
    """Base class for syntax probes."""

    def __init__(self):
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if the required tools are available."""
        raise NotImplementedError

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        """Check a file for syntax issues."""
        raise NotImplementedError

    def get_supported_extensions(self) -> set:
        """Get file extensions supported by this probe."""
        raise NotImplementedError


class ClangSyntaxProbe(SyntaxProbe):
    """C/C++ syntax checking using clang."""

    def _check_availability(self) -> bool:
        return shutil.which("clang") is not None

    def get_supported_extensions(self) -> set:
        return {'.c', '.cpp', '.cxx', '.cc', '.C', '.c++', '.h', '.hpp', '.hxx', '.hh', '.H', '.h++'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        findings = []
        try:
            # Use clang for basic syntax checking
            cmd = ["clang", "-fsyntax-only", "-fno-color-diagnostics", str(file_path)]

            # Try to use compile_commands.json if available
            compile_db = pathlib.Path.cwd() / "exports" / "compile_commands.json"
            if compile_db.exists():
                cmd.extend(["-p", str(compile_db.parent)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0 and result.stderr:
                # Parse clang error output
                findings.extend(self._parse_clang_output(file_path, result.stderr))

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            # If clang fails, report a generic syntax error
            findings.append(Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="syntax_check_failed",
                symbol="",
                message="C/C++ syntax check failed or timed out",
                severity="warning"
            ))

        return findings

    def _parse_clang_output(self, file_path: pathlib.Path, stderr: str) -> List[Finding]:
        """Parse clang diagnostic output into findings."""
        findings = []
        lines = stderr.strip().split('\n')

        for line in lines:
            if ':' in line and ('error:' in line or 'warning:' in line):
                try:
                    # Parse format: file:line:col: error/warning: message
                    parts = line.split(':', 4)
                    if len(parts) >= 4:
                        file_part = parts[0]
                        line_num = int(parts[1])
                        col_num = int(parts[2])
                        severity = "error" if "error:" in parts[3] else "warning"
                        message = parts[4].strip() if len(parts) > 4 else parts[3]

                        # Clean up the message
                        if message.startswith("error:"):
                            message = message[6:].strip()
                        elif message.startswith("warning:"):
                            message = message[8:].strip()

                        findings.append(Finding(
                            file=str(file_path),
                            line=line_num,
                            col=col_num,
                            rule="clang_syntax",
                            symbol="",
                            message=message,
                            severity=severity
                        ))
                except (ValueError, IndexError):
                    # Skip malformed lines
                    continue

        return findings


class JsonSyntaxProbe(SyntaxProbe):
    """JSON syntax checking using jq."""

    def _check_availability(self) -> bool:
        return shutil.which("jq") is not None

    def get_supported_extensions(self) -> set:
        return {'.json'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        try:
            result = subprocess.run(
                ["jq", ".", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                # Parse jq error message
                error_msg = result.stderr.strip()
                return [Finding(
                    file=str(file_path),
                    line=1,
                    col=1,
                    rule="json_syntax",
                    symbol="",
                    message=f"JSON syntax error: {error_msg}",
                    severity="error"
                )]

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return [Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="json_check_failed",
                symbol="",
                message="JSON syntax check failed",
                severity="warning"
            )]

        return []


class YamlSyntaxProbe(SyntaxProbe):
    """YAML syntax checking using yamllint."""

    def _check_availability(self) -> bool:
        return shutil.which("yamllint") is not None

    def get_supported_extensions(self) -> set:
        return {'.yaml', '.yml'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        try:
            result = subprocess.run(
                ["yamllint", "--format", "parsable", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            findings = []
            if result.stdout:
                # Parse yamllint output
                for line in result.stdout.strip().split('\n'):
                    if line and ':' in line:
                        findings.extend(self._parse_yamllint_line(file_path, line))

            return findings

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return [Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="yaml_check_failed",
                symbol="",
                message="YAML syntax check failed",
                severity="warning"
            )]

    def _parse_yamllint_line(self, file_path: pathlib.Path, line: str) -> List[Finding]:
        """Parse yamllint output line."""
        try:
            # Format: file:line:col: [level] message (rule)
            parts = line.split(':', 3)
            if len(parts) >= 4:
                line_num = int(parts[1])
                col_num = int(parts[2])
                rest = parts[3].strip()

                # Extract severity and message
                if rest.startswith('[error]'):
                    severity = "error"
                    message = rest[7:].strip()
                elif rest.startswith('[warning]'):
                    severity = "warning"
                    message = rest[9:].strip()
                else:
                    severity = "warning"
                    message = rest

                return [Finding(
                    file=str(file_path),
                    line=line_num,
                    col=col_num,
                    rule="yaml_syntax",
                    symbol="",
                    message=message,
                    severity=severity
                )]
        except (ValueError, IndexError):
            pass

        return []


class TomlSyntaxProbe(SyntaxProbe):
    """TOML syntax checking using taplo."""

    def _check_availability(self) -> bool:
        return shutil.which("taplo") is not None

    def get_supported_extensions(self) -> set:
        return {'.toml'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        try:
            result = subprocess.run(
                ["taplo", "check", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return [Finding(
                    file=str(file_path),
                    line=1,
                    col=1,
                    rule="toml_syntax",
                    symbol="",
                    message=f"TOML syntax error: {error_msg}",
                    severity="error"
                )]

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return [Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="toml_check_failed",
                symbol="",
                message="TOML syntax check failed",
                severity="warning"
            )]

        return []


class ShellSyntaxProbe(SyntaxProbe):
    """Shell script syntax checking using bash -n."""

    def _check_availability(self) -> bool:
        return shutil.which("bash") is not None

    def get_supported_extensions(self) -> set:
        return {'.sh', '.bash'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        try:
            result = subprocess.run(
                ["bash", "-n", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                return [Finding(
                    file=str(file_path),
                    line=1,
                    col=1,
                    rule="shell_syntax",
                    symbol="",
                    message=f"Shell syntax error: {error_msg}",
                    severity="error"
                )]

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return [Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="shell_check_failed",
                symbol="",
                message="Shell syntax check failed",
                severity="warning"
            )]

        return []


def get_syntax_probes() -> List[SyntaxProbe]:
    """Get all available syntax probes."""
    probes = [
        ClangSyntaxProbe(),
        JsonSyntaxProbe(),
        YamlSyntaxProbe(),
        TomlSyntaxProbe(),
        ShellSyntaxProbe()
    ]
    return [probe for probe in probes if probe.available]


def get_probe_for_file(file_path: pathlib.Path, probes: List[SyntaxProbe]) -> Optional[SyntaxProbe]:
    """Get the appropriate syntax probe for a file."""
    extension = file_path.suffix.lower()
    for probe in probes:
        if extension in probe.get_supported_extensions():
            return probe
    return None