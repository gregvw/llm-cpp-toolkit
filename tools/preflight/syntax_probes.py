"""
External syntax checking probes for llmtk preflight

Implements fast syntax checking using external tools like clang, jq, etc.
"""

import pathlib
import subprocess
import shutil
from typing import List, Optional, Dict, Any, Tuple
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

    def __init__(self):
        super().__init__()
        self.compile_db_cache = None
        self.compile_db_path = None

    def _check_availability(self) -> bool:
        return shutil.which("clang") is not None

    def get_supported_extensions(self) -> set:
        return {'.c', '.cpp', '.cxx', '.cc', '.C', '.c++', '.h', '.hpp', '.hxx', '.hh', '.H', '.h++'}

    def _load_compile_commands(self) -> Optional[Dict[str, Any]]:
        """Load and cache compile_commands.json."""
        # Check multiple possible locations
        possible_paths = [
            pathlib.Path.cwd() / "exports" / "compile_commands.json",
            pathlib.Path.cwd() / "compile_commands.json",
            pathlib.Path.cwd() / "build" / "compile_commands.json"
        ]

        for path in possible_paths:
            if path.exists():
                try:
                    if self.compile_db_path != path or self.compile_db_cache is None:
                        import json
                        self.compile_db_cache = json.loads(path.read_text())
                        self.compile_db_path = path
                    return self.compile_db_cache
                except Exception:
                    continue
        return None

    def _get_compile_entry(self, file_path: pathlib.Path) -> Optional[Dict[str, Any]]:
        """Get compile command entry for a specific file."""
        compile_db = self._load_compile_commands()
        if not compile_db:
            return None

        file_abs = file_path.resolve()
        for entry in compile_db:
            entry_file = pathlib.Path(entry.get("file", "")).resolve()
            if entry_file == file_abs:
                return entry

        return None

    def _build_clang_command(self, file_path: pathlib.Path) -> Tuple[List[str], Optional[str]]:
        """Build clang command with appropriate flags."""
        cmd = ["clang", "-fsyntax-only", "-fno-color-diagnostics"]

        # Try to get compile command from compile_commands.json
        compile_entry = self._get_compile_entry(file_path)
        if compile_entry:
            # Extract useful flags from the compile command
            command = compile_entry.get("command", "")
            if command:
                # Parse compile command to extract include paths and defines
                import shlex
                try:
                    compile_args = shlex.split(command)
                    useful_flags = []
                    i = 0
                    while i < len(compile_args):
                        arg = compile_args[i]
                        # Include useful compilation flags
                        if arg.startswith(('-I', '-D', '-std=', '-stdlib=', '-isystem')):
                            useful_flags.append(arg)
                        elif arg in ('-I', '-D', '-isystem', '-include'):
                            useful_flags.extend([arg, compile_args[i + 1]])
                            i += 1
                        elif arg.startswith('-std'):
                            useful_flags.append(arg)
                        i += 1

                    cmd.extend(useful_flags)
                except Exception:
                    pass  # Fall back to basic command

            # Set working directory if available
            working_dir = compile_entry.get("directory")
            if working_dir:
                # Convert file path relative to compile command working directory
                try:
                    rel_path = file_path.relative_to(pathlib.Path(working_dir))
                    cmd.append(str(rel_path))
                    return cmd, working_dir
                except ValueError:
                    pass  # File not relative to working directory

        # Fallback: use absolute path
        cmd.append(str(file_path))
        return cmd, None

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        findings = []
        try:
            cmd, working_dir = self._build_clang_command(file_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=working_dir
            )

            if result.returncode != 0 and result.stderr:
                # Parse clang error output
                findings.extend(self._parse_clang_output(file_path, result.stderr))

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            # If clang fails, report a more specific error
            error_msg = f"C/C++ syntax check failed: {str(e)}"
            findings.append(Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="syntax_check_failed",
                symbol="",
                message=error_msg,
                severity="warning",
                source="clang"
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
                            severity=severity,
                            source="clang"
                        ))
                except (ValueError, IndexError):
                    # Skip malformed lines
                    continue

        return findings


class JsonSyntaxProbe(SyntaxProbe):
    """JSON syntax checking using jq and Python's json module."""

    def _check_availability(self) -> bool:
        # JSON checking always available via Python's json module
        return True

    def get_supported_extensions(self) -> set:
        return {'.json'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        findings = []

        # First try Python's json module for precise error location
        try:
            import json
            content = file_path.read_text(encoding='utf-8')
            json.loads(content)
        except json.JSONDecodeError as e:
            findings.append(Finding(
                file=str(file_path),
                line=e.lineno,
                col=e.colno,
                rule="json_syntax",
                symbol="",
                message=f"JSON parse error: {e.msg}",
                severity="error"
            ))
            return findings
        except Exception as e:
            findings.append(Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="json_read_error",
                symbol="",
                message=f"Could not read JSON file: {str(e)}",
                severity="error"
            ))
            return findings

        # If Python parsing succeeds, optionally use jq for additional validation
        if shutil.which("jq"):
            try:
                result = subprocess.run(
                    ["jq", ".", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    # Parse jq error for additional issues
                    error_msg = result.stderr.strip()
                    if error_msg and "parse error" in error_msg.lower():
                        findings.append(Finding(
                            file=str(file_path),
                            line=1,
                            col=1,
                            rule="json_jq_validation",
                            symbol="",
                            message=f"JSON validation warning: {error_msg}",
                            severity="warning"
                        ))

            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass  # jq failure is not critical if Python parsing succeeded

        return findings


class YamlSyntaxProbe(SyntaxProbe):
    """YAML syntax checking using yamllint and Python's yaml module."""

    def _check_availability(self) -> bool:
        # Try PyYAML first, fall back to yamllint
        try:
            import yaml
            return True
        except ImportError:
            return shutil.which("yamllint") is not None

    def get_supported_extensions(self) -> set:
        return {'.yaml', '.yml'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        findings = []

        # First try Python's yaml module for basic syntax checking
        try:
            import yaml
            content = file_path.read_text(encoding='utf-8')
            # Use safe_load to parse YAML
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            # Parse YAML error for line/column information
            line_num = 1
            col_num = 1
            message = str(e)

            if hasattr(e, 'problem_mark') and e.problem_mark:
                line_num = e.problem_mark.line + 1  # Convert to 1-based
                col_num = e.problem_mark.column + 1

            findings.append(Finding(
                file=str(file_path),
                line=line_num,
                col=col_num,
                rule="yaml_syntax",
                symbol="",
                message=f"YAML parse error: {message}",
                severity="error"
            ))
            return findings
        except ImportError:
            # PyYAML not available, fall back to yamllint
            pass
        except Exception as e:
            findings.append(Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="yaml_read_error",
                symbol="",
                message=f"Could not read YAML file: {str(e)}",
                severity="error"
            ))
            return findings

        # If PyYAML parsing succeeds or isn't available, use yamllint for style checks
        if shutil.which("yamllint"):
            try:
                result = subprocess.run(
                    ["yamllint", "--format", "parsable", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.stdout:
                    # Parse yamllint output
                    for line in result.stdout.strip().split('\n'):
                        if line and ':' in line:
                            yamllint_findings = self._parse_yamllint_line(file_path, line)
                            findings.extend(yamllint_findings)

            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                if not findings:  # Only report failure if we don't have PyYAML results
                    findings.append(Finding(
                        file=str(file_path),
                        line=1,
                        col=1,
                        rule="yaml_check_failed",
                        symbol="",
                        message="YAML syntax check failed",
                        severity="warning"
                    ))

        return findings

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

                # Extract rule name if present
                rule = "yaml_style"
                if '(' in message and message.endswith(')'):
                    rule_match = message.rfind('(')
                    if rule_match != -1:
                        rule = message[rule_match+1:-1]
                        message = message[:rule_match].strip()

                return [Finding(
                    file=str(file_path),
                    line=line_num,
                    col=col_num,
                    rule=f"yaml_{rule}",
                    symbol="",
                    message=message,
                    severity=severity
                )]
        except (ValueError, IndexError):
            pass

        return []


class TomlSyntaxProbe(SyntaxProbe):
    """TOML syntax checking using Python's tomllib/tomli and taplo."""

    def _check_availability(self) -> bool:
        # Try Python's built-in tomllib (3.11+) or tomli package, fall back to taplo
        try:
            try:
                import tomllib  # Python 3.11+
                return True
            except ImportError:
                import tomli  # Fallback package
                return True
        except ImportError:
            return shutil.which("taplo") is not None

    def get_supported_extensions(self) -> set:
        return {'.toml'}

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        findings = []

        # First try Python's TOML parsing for precise error location
        try:
            try:
                import tomllib  # Python 3.11+
                toml_module = tomllib
            except ImportError:
                import tomli as toml_module  # Fallback

            with open(file_path, 'rb') as f:
                toml_module.load(f)

        except Exception as e:
            # Parse TOML error - most TOML libraries provide line information
            line_num = 1
            col_num = 1
            message = str(e)

            # Try to extract line number from error message
            import re
            line_match = re.search(r'line (\d+)', message, re.IGNORECASE)
            if line_match:
                line_num = int(line_match.group(1))

            col_match = re.search(r'column (\d+)', message, re.IGNORECASE)
            if col_match:
                col_num = int(col_match.group(1))

            findings.append(Finding(
                file=str(file_path),
                line=line_num,
                col=col_num,
                rule="toml_syntax",
                symbol="",
                message=f"TOML parse error: {message}",
                severity="error"
            ))
            return findings

        # If Python parsing succeeds, optionally use taplo for additional validation
        if shutil.which("taplo"):
            try:
                result = subprocess.run(
                    ["taplo", "check", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or result.stdout.strip()
                    if error_msg:
                        # Try to parse taplo output for line/column info
                        line_num = 1
                        col_num = 1

                        # Taplo often includes location info in format "line:col"
                        import re
                        location_match = re.search(r'(\d+):(\d+)', error_msg)
                        if location_match:
                            line_num = int(location_match.group(1))
                            col_num = int(location_match.group(2))

                        findings.append(Finding(
                            file=str(file_path),
                            line=line_num,
                            col=col_num,
                            rule="toml_taplo_validation",
                            symbol="",
                            message=f"TOML validation warning: {error_msg}",
                            severity="warning"
                        ))

            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass  # taplo failure is not critical if Python parsing succeeded

        return findings


class ShellSyntaxProbe(SyntaxProbe):
    """Shell script syntax checking using bash -n and shellcheck."""

    def _check_availability(self) -> bool:
        # bash -n is always preferred as it's most commonly available
        return shutil.which("bash") is not None

    def get_supported_extensions(self) -> set:
        return {'.sh', '.bash', '.zsh'}

    def _detect_shell_type(self, file_path: pathlib.Path) -> str:
        """Detect shell type from shebang or extension."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#!'):
                    if 'zsh' in first_line:
                        return 'zsh'
                    elif 'bash' in first_line:
                        return 'bash'
                    elif 'sh' in first_line:
                        return 'sh'
        except Exception:
            pass

        # Fall back to extension
        ext = file_path.suffix.lower()
        if ext == '.zsh':
            return 'zsh'
        elif ext == '.bash':
            return 'bash'
        else:
            return 'sh'

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        findings = []
        shell_type = self._detect_shell_type(file_path)

        # First try basic syntax checking with appropriate shell
        shell_cmd = shell_type if shutil.which(shell_type) else 'bash'

        try:
            result = subprocess.run(
                [shell_cmd, "-n", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                # Parse shell error for line information
                line_num = 1

                import re
                # Look for line numbers in format "file: line N:" or "line N:"
                line_match = re.search(r'line (\d+)', error_msg, re.IGNORECASE)
                if line_match:
                    line_num = int(line_match.group(1))

                findings.append(Finding(
                    file=str(file_path),
                    line=line_num,
                    col=1,
                    rule="shell_syntax",
                    symbol="",
                    message=f"Shell syntax error: {error_msg}",
                    severity="error"
                ))

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            findings.append(Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="shell_check_failed",
                symbol="",
                message=f"Shell syntax check failed: {str(e)}",
                severity="warning"
            ))

        # If shellcheck is available, use it for additional static analysis
        if shutil.which("shellcheck"):
            try:
                result = subprocess.run(
                    ["shellcheck", "--format=gcc", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=15
                )

                if result.stdout:
                    # Parse shellcheck output (GCC format)
                    for line in result.stdout.strip().split('\n'):
                        if line and ':' in line:
                            shellcheck_finding = self._parse_shellcheck_line(file_path, line)
                            if shellcheck_finding:
                                findings.append(shellcheck_finding)

            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass  # shellcheck failure is not critical

        return findings

    def _parse_shellcheck_line(self, file_path: pathlib.Path, line: str) -> Optional[Finding]:
        """Parse shellcheck GCC-format output."""
        try:
            # Format: file:line:col: level: message [SC####]
            parts = line.split(':', 4)
            if len(parts) >= 5:
                line_num = int(parts[1])
                col_num = int(parts[2])
                level_and_msg = parts[4].strip()

                # Extract level and message
                if level_and_msg.startswith('error:'):
                    severity = "error"
                    message = level_and_msg[6:].strip()
                elif level_and_msg.startswith('warning:'):
                    severity = "warning"
                    message = level_and_msg[8:].strip()
                elif level_and_msg.startswith('note:'):
                    severity = "warning"
                    message = level_and_msg[5:].strip()
                else:
                    severity = "warning"
                    message = level_and_msg

                # Extract rule code if present
                rule = "shellcheck"
                import re
                rule_match = re.search(r'\[SC(\d+)\]', message)
                if rule_match:
                    rule = f"shellcheck_SC{rule_match.group(1)}"
                    message = re.sub(r'\s*\[SC\d+\]', '', message).strip()

                return Finding(
                    file=str(file_path),
                    line=line_num,
                    col=col_num,
                    rule=rule,
                    symbol="",
                    message=message,
                    severity=severity
                )
        except (ValueError, IndexError):
            pass

        return None


class CMakeSyntaxProbe(SyntaxProbe):
    """CMake syntax checking using cmake --check-syntax."""

    def _check_availability(self) -> bool:
        return shutil.which("cmake") is not None

    def get_supported_extensions(self) -> set:
        return {'.cmake'}

    def _is_cmake_file(self, file_path: pathlib.Path) -> bool:
        """Check if file is a CMake file."""
        if file_path.suffix.lower() == '.cmake':
            return True
        if file_path.name.lower() in ('cmakelists.txt', 'cmake.txt'):
            return True
        return False

    def check_file(self, file_path: pathlib.Path) -> List[Finding]:
        if not self.available:
            return []

        if not self._is_cmake_file(file_path):
            return []

        findings = []

        # Basic CMake syntax checking
        try:
            # Create a temporary file for cmake to check
            # (cmake sometimes has issues with direct file checking)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cmake', delete=False) as tmp:
                content = file_path.read_text(encoding='utf-8')
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Use cmake to check syntax
                result = subprocess.run(
                    ["cmake", "-P", tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0 and result.stderr:
                    # Parse cmake error output
                    findings.extend(self._parse_cmake_output(file_path, result.stderr))

            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            findings.append(Finding(
                file=str(file_path),
                line=1,
                col=1,
                rule="cmake_check_failed",
                symbol="",
                message=f"CMake syntax check failed: {str(e)}",
                severity="warning"
            ))

        # Additional cmake-format checking if available
        if shutil.which("cmake-format"):
            try:
                result = subprocess.run(
                    ["cmake-format", "--check", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or result.stdout.strip()
                    if error_msg:
                        findings.append(Finding(
                            file=str(file_path),
                            line=1,
                            col=1,
                            rule="cmake_format",
                            symbol="",
                            message=f"CMake format issue: {error_msg}",
                            severity="warning"
                        ))

            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass  # cmake-format failure is not critical

        return findings

    def _parse_cmake_output(self, file_path: pathlib.Path, stderr: str) -> List[Finding]:
        """Parse cmake error output."""
        findings = []
        lines = stderr.strip().split('\n')

        for line in lines:
            if 'error' in line.lower() or 'parse error' in line.lower():
                # Try to extract line number
                line_num = 1
                import re

                # Look for patterns like "line 123" or ":123:"
                line_match = re.search(r'line (\d+)', line, re.IGNORECASE)
                if not line_match:
                    line_match = re.search(r':(\d+):', line)

                if line_match:
                    line_num = int(line_match.group(1))

                # Clean up the error message
                message = line
                # Remove file paths and common prefixes
                if str(file_path) in message:
                    message = message.replace(str(file_path), '').strip()
                if message.startswith(':'):
                    message = message[1:].strip()

                findings.append(Finding(
                    file=str(file_path),
                    line=line_num,
                    col=1,
                    rule="cmake_syntax",
                    symbol="",
                    message=f"CMake error: {message}",
                    severity="error"
                ))

        return findings


def get_syntax_probes() -> List[SyntaxProbe]:
    """Get all available syntax probes."""
    probes = [
        ClangSyntaxProbe(),
        JsonSyntaxProbe(),
        YamlSyntaxProbe(),
        TomlSyntaxProbe(),
        ShellSyntaxProbe(),
        CMakeSyntaxProbe()
    ]
    return [probe for probe in probes if probe.available]


def get_probe_for_file(file_path: pathlib.Path, probes: List[SyntaxProbe]) -> Optional[SyntaxProbe]:
    """Get the appropriate syntax probe for a file."""
    extension = file_path.suffix.lower()
    filename = file_path.name.lower()

    for probe in probes:
        if extension in probe.get_supported_extensions():
            return probe
        # Special handling for CMake files
        if isinstance(probe, CMakeSyntaxProbe) and probe._is_cmake_file(file_path):
            return probe

    return None