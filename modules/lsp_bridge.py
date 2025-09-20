#!/usr/bin/env python3
"""
LSP Bridge for clangd - provides structured diagnostics with filtering.

This module implements a Language Server Protocol client specifically for clangd,
collecting diagnostics and filtering them consistently with stderr-thin functionality.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse
from urllib.request import pathname2url


class LSPError(Exception):
    """Exception raised for LSP-related errors."""
    pass


class ClangdClient:
    """Simple LSP client for clangd to collect diagnostics."""

    def __init__(self, server_path: Optional[str] = None, timeout: float = 30.0):
        self.server_path = server_path or self._find_clangd()
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self.next_id = 1
        self.diagnostics: Dict[str, List[Dict]] = {}
        self.server_info: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def _find_clangd(self) -> str:
        """Find clangd executable."""
        candidates = ["clangd", "clangd-18", "clangd-17", "clangd-16", "clangd-15"]
        for candidate in candidates:
            if shutil.which(candidate):
                return candidate
        raise LSPError("clangd not found in PATH")

    def _file_to_uri(self, file_path: Union[str, pathlib.Path]) -> str:
        """Convert file path to file:// URI."""
        abs_path = pathlib.Path(file_path).resolve()
        return f"file://{pathname2url(str(abs_path))}"

    def _uri_to_file(self, uri: str) -> str:
        """Convert file:// URI to file path."""
        parsed = urlparse(uri)
        return parsed.path

    def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send LSP request and return response."""
        if not self.process:
            raise LSPError("LSP server not started")

        request_id = self.next_id
        self.next_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }

        message = json.dumps(request)
        content_length = len(message.encode('utf-8'))

        # Send request
        try:
            full_message = f"Content-Length: {content_length}\r\n\r\n{message}".encode('utf-8')
            self.process.stdin.write(full_message)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise LSPError(f"Failed to send request: {e}")

        # Read response
        response = self._read_response()
        if "error" in response:
            error = response["error"]
            raise LSPError(f"LSP error {error.get('code', 'unknown')}: {error.get('message', 'no message')}")

        return response.get("result", {})

    def _send_notification(self, method: str, params: Optional[Dict] = None) -> None:
        """Send LSP notification (no response expected)."""
        if not self.process:
            raise LSPError("LSP server not started")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }

        message = json.dumps(notification)
        content_length = len(message.encode('utf-8'))

        try:
            full_message = f"Content-Length: {content_length}\r\n\r\n{message}".encode('utf-8')
            self.process.stdin.write(full_message)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise LSPError(f"Failed to send notification: {e}")

    def _read_response(self) -> Dict:
        """Read LSP response from server."""
        if not self.process or not self.process.stdout:
            raise LSPError("LSP server not available")

        # Read headers
        headers = {}
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise LSPError("Server closed connection")
            line = line.strip()
            if not line:
                break
            if b':' in line:
                key, value = line.split(b':', 1)
                headers[key.decode().strip().lower()] = value.decode().strip()

        # Read content
        content_length = int(headers.get('content-length', 0))
        if content_length <= 0:
            raise LSPError("Invalid content-length")

        content = self.process.stdout.read(content_length)
        if len(content) != content_length:
            raise LSPError("Incomplete message received")

        try:
            return json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise LSPError(f"Invalid JSON response: {e}")

    def start(self) -> None:
        """Start clangd server."""
        try:
            self.process = subprocess.Popen(
                [self.server_path, "--log=error"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False
            )
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            raise LSPError(f"Failed to start clangd: {e}")

        # Initialize server
        try:
            capabilities = self._send_request("initialize", {
                "processId": os.getpid(),
                "clientInfo": {"name": "llmtk", "version": "1.0"},
                "capabilities": {
                    "textDocument": {
                        "publishDiagnostics": {"diagnosticPullSupport": False}
                    }
                },
                "workspaceFolders": [{
                    "uri": self._file_to_uri(pathlib.Path.cwd()),
                    "name": "workspace"
                }]
            })

            self.server_info = {
                "capabilities": capabilities,
                "version": self._get_server_version()
            }

            # Send initialized notification
            self._send_notification("initialized", {})

        except Exception as e:
            self.stop()
            raise LSPError(f"Failed to initialize server: {e}")

    def stop(self) -> None:
        """Stop clangd server."""
        if self.process:
            try:
                self._send_notification("shutdown", {})
                self._send_notification("exit", {})
            except:
                pass  # Server may already be dead

            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                    self.process.wait()
                except:
                    pass

            self.process = None

    def _get_server_version(self) -> Optional[str]:
        """Try to get clangd version."""
        try:
            result = subprocess.run(
                [self.server_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        return None

    def analyze_file(self, file_path: Union[str, pathlib.Path], compile_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze a single file and collect diagnostics."""
        file_path = pathlib.Path(file_path).resolve()
        if not file_path.exists():
            raise LSPError(f"File not found: {file_path}")

        uri = self._file_to_uri(file_path)

        try:
            # Read file content
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            raise LSPError(f"Failed to read file {file_path}: {e}")

        start_time = time.time()
        file_diagnostics = []

        try:
            # Open document
            self._send_notification("textDocument/didOpen", {
                "textDocument": {
                    "uri": uri,
                    "languageId": "cpp",
                    "version": 1,
                    "text": content
                }
            })

            # Wait for diagnostics (simple approach - wait and read notifications)
            deadline = time.time() + min(self.timeout, 10)  # Max 10 seconds per file

            while time.time() < deadline:
                try:
                    # Try to read any notifications
                    message = self._read_response()
                    if message.get("method") == "textDocument/publishDiagnostics":
                        params = message.get("params", {})
                        if params.get("uri") == uri:
                            file_diagnostics = params.get("diagnostics", [])
                            break
                except:
                    # No more messages or timeout
                    time.sleep(0.1)
                    continue

            # Close document
            self._send_notification("textDocument/didClose", {
                "textDocument": {"uri": uri}
            })

        except Exception as e:
            raise LSPError(f"Failed to analyze file {file_path}: {e}")

        processing_time = (time.time() - start_time) * 1000  # ms

        return {
            "file": str(file_path),
            "uri": uri,
            "diagnostics": file_diagnostics,
            "diagnostics_count": len(file_diagnostics),
            "processing_time_ms": round(processing_time, 2),
            "status": "success"
        }


def normalize_lsp_diagnostic(diag: Dict, file_path: str) -> Dict:
    """Normalize LSP diagnostic to stderr-thin compatible format."""
    severity_map = {
        1: "error",      # DiagnosticSeverity.Error
        2: "warning",    # DiagnosticSeverity.Warning
        3: "information", # DiagnosticSeverity.Information
        4: "hint"        # DiagnosticSeverity.Hint
    }

    severity_num = diag.get("severity", 3)
    severity_name = severity_map.get(severity_num, "information")

    range_info = diag.get("range", {})
    start = range_info.get("start", {})
    end = range_info.get("end", {})

    # Convert to stderr-thin format
    normalized = {
        "level": severity_name,
        "message": diag.get("message", ""),
        "file": file_path,
        "line": start.get("line", 0) + 1,  # LSP uses 0-based lines
        "column": start.get("character", 0) + 1,  # LSP uses 0-based characters
        "category": diag.get("source"),
        "option": diag.get("code"),
        "notes": [],
        "raw": json.dumps(diag),
        # Keep original LSP fields
        "lsp_severity": severity_num,
        "lsp_range": range_info,
        "lsp_tags": diag.get("tags", []),
        "lsp_related": diag.get("relatedInformation", []),
        "lsp_data": diag.get("data")
    }

    # Add related information as notes
    for related in diag.get("relatedInformation", []):
        if "location" in related and "message" in related:
            location = related["location"]
            rel_range = location.get("range", {})
            rel_start = rel_range.get("start", {})
            rel_file = pathlib.Path(location.get("uri", "").replace("file://", "")).name

            note = {
                "level": "note",
                "message": related["message"],
                "file": rel_file,
                "line": rel_start.get("line", 0) + 1,
                "column": rel_start.get("character", 0) + 1,
                "category": None,
                "option": None
            }
            normalized["notes"].append(note)

    return normalized


def collect_diagnostics(
    files: List[str],
    compile_db_path: Optional[str] = None,
    server_path: Optional[str] = None,
    timeout: float = 30.0
) -> Dict[str, Any]:
    """Collect diagnostics from clangd for given files."""
    client = ClangdClient(server_path=server_path, timeout=timeout)

    try:
        client.start()

        results = {
            "server_info": {
                "path": client.server_path,
                "version": client.server_info.get("version"),
                "capabilities": client.server_info.get("capabilities")
            },
            "files": [],
            "diagnostics": [],
            "counts": {"error": 0, "warning": 0, "information": 0, "hint": 0, "total": 0}
        }

        for file_path in files:
            try:
                file_result = client.analyze_file(file_path)
                results["files"].append(file_result)

                # Process diagnostics
                for diag in file_result["diagnostics"]:
                    normalized = normalize_lsp_diagnostic(diag, file_result["file"])
                    results["diagnostics"].append(normalized)

                    # Update counts
                    severity = normalized["level"]
                    if severity in results["counts"]:
                        results["counts"][severity] += 1
                    results["counts"]["total"] += 1

            except Exception as e:
                error_result = {
                    "file": str(file_path),
                    "uri": f"file://{pathname2url(str(pathlib.Path(file_path).resolve()))}",
                    "diagnostics_count": 0,
                    "processing_time_ms": 0,
                    "status": f"error: {e}"
                }
                results["files"].append(error_result)

        return results

    finally:
        client.stop()


