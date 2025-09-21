"""Agent command for llmtk - JSON request handler and MCP server."""

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.context import get_exports_dir, get_project_root
from ..core.dry_run import is_dry_run
from ..core.utils import write_json


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the agent command and subcommands."""
    parser = subparsers.add_parser("agent", help="Agent operations for LLM integration")
    agent_subparsers = parser.add_subparsers(dest="agent_cmd", required=True)

    # agent request subcommand
    request_parser = agent_subparsers.add_parser(
        "request",
        help="Process structured JSON requests"
    )
    request_parser.add_argument(
        "request_json",
        help="JSON request string or '-' for stdin"
    )
    request_parser.set_defaults(func=_handle_request)

    # agent mcp subcommand
    mcp_parser = agent_subparsers.add_parser(
        "mcp",
        help="Start MCP (Model Context Protocol) server over stdio"
    )
    mcp_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds for individual operations (default: 30)"
    )
    mcp_parser.set_defaults(func=_handle_mcp)


def _handle_request(args: argparse.Namespace) -> int:
    """Handle structured JSON request."""
    try:
        if args.request_json == "-":
            request_data = json.load(sys.stdin)
        else:
            request_data = json.loads(args.request_json)

        response = _process_requests(request_data)
        json.dump(response, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        error_response = {
            "error": {
                "type": "internal_error",
                "message": str(e)
            }
        }
        json.dump(error_response, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1


def _handle_mcp(args: argparse.Namespace) -> int:
    """Handle MCP protocol over stdio."""
    try:
        mcp_server = MCPServer(timeout=args.timeout)
        return mcp_server.run()
    except Exception as e:
        print(f"Error: MCP server failed: {e}", file=sys.stderr)
        return 1


def _process_requests(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a batch of agent requests."""
    if "requests" not in data or not isinstance(data["requests"], list):
        return {
            "error": {
                "type": "invalid_request",
                "message": "Missing or invalid 'requests' array"
            }
        }

    responses = []
    for request in data["requests"]:
        response = _process_single_request(request)
        responses.append(response)

    return {"responses": responses}


def _process_single_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single agent request."""
    request_id = request.get("id", "unknown")
    kind = request.get("kind")
    params = request.get("params", {})

    if not kind:
        return {
            "id": request_id,
            "status": "error",
            "error": "Missing 'kind' field"
        }

    try:
        if kind == "read_file":
            return _handle_read_file(request_id, params)
        elif kind == "write_file":
            return _handle_write_file(request_id, params)
        elif kind == "delete_file":
            return _handle_delete_file(request_id, params)
        elif kind == "list_directory":
            return _handle_list_directory(request_id, params)
        elif kind == "list_exports":
            return _handle_list_exports(request_id, params)
        elif kind == "get_capabilities":
            return _handle_get_capabilities(request_id, params)
        elif kind == "expand_context":
            return _handle_expand_context(request_id, params)
        else:
            return {
                "id": request_id,
                "status": "error",
                "error": f"Unknown request kind: {kind}"
            }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": str(e)
        }


def _safe_path(path: str) -> Optional[Path]:
    """Validate and resolve path relative to project root."""
    project_root = get_project_root()
    try:
        # Convert to absolute path and resolve
        if Path(path).is_absolute():
            resolved = Path(path).resolve()
        else:
            resolved = (project_root / path).resolve()

        # Ensure path is within project root
        resolved.relative_to(project_root)
        return resolved
    except (ValueError, OSError):
        return None


def _handle_read_file(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle read_file request."""
    path_str = params.get("path")
    if not path_str:
        return {
            "id": request_id,
            "status": "error",
            "error": "Missing 'path' parameter"
        }

    path = _safe_path(path_str)
    if not path:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Invalid or unsafe path: {path_str}"
        }

    if not path.exists():
        return {
            "id": request_id,
            "status": "error",
            "error": f"File not found: {path_str}"
        }

    if not path.is_file():
        return {
            "id": request_id,
            "status": "error",
            "error": f"Path is not a file: {path_str}"
        }

    try:
        content = path.read_text(encoding="utf-8")
        return {
            "id": request_id,
            "status": "success",
            "data": {
                "path": path_str,
                "content": content,
                "size": len(content)
            }
        }
    except UnicodeDecodeError:
        return {
            "id": request_id,
            "status": "error",
            "error": f"File is not valid UTF-8: {path_str}"
        }


def _handle_write_file(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle write_file request."""
    path_str = params.get("path")
    content = params.get("content")

    if not path_str:
        return {
            "id": request_id,
            "status": "error",
            "error": "Missing 'path' parameter"
        }

    if content is None:
        return {
            "id": request_id,
            "status": "error",
            "error": "Missing 'content' parameter"
        }

    path = _safe_path(path_str)
    if not path:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Invalid or unsafe path: {path_str}"
        }

    if is_dry_run():
        return {
            "id": request_id,
            "status": "success",
            "data": {
                "path": path_str,
                "action": "write",
                "dry_run": True,
                "size": len(str(content))
            }
        }

    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(str(content), encoding="utf-8")
        return {
            "id": request_id,
            "status": "success",
            "data": {
                "path": path_str,
                "action": "write",
                "size": len(str(content))
            }
        }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Failed to write file: {e}"
        }


def _handle_delete_file(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle delete_file request."""
    path_str = params.get("path")
    if not path_str:
        return {
            "id": request_id,
            "status": "error",
            "error": "Missing 'path' parameter"
        }

    path = _safe_path(path_str)
    if not path:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Invalid or unsafe path: {path_str}"
        }

    if not path.exists():
        return {
            "id": request_id,
            "status": "success",
            "data": {
                "path": path_str,
                "action": "delete",
                "existed": False
            }
        }

    if is_dry_run():
        return {
            "id": request_id,
            "status": "success",
            "data": {
                "path": path_str,
                "action": "delete",
                "dry_run": True,
                "existed": True
            }
        }

    try:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()  # Only empty directories
        else:
            return {
                "id": request_id,
                "status": "error",
                "error": f"Path is neither file nor directory: {path_str}"
            }

        return {
            "id": request_id,
            "status": "success",
            "data": {
                "path": path_str,
                "action": "delete",
                "existed": True
            }
        }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Failed to delete: {e}"
        }


def _handle_list_directory(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle list_directory request."""
    path_str = params.get("path", ".")

    path = _safe_path(path_str)
    if not path:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Invalid or unsafe path: {path_str}"
        }

    if not path.exists():
        return {
            "id": request_id,
            "status": "error",
            "error": f"Directory not found: {path_str}"
        }

    if not path.is_dir():
        return {
            "id": request_id,
            "status": "error",
            "error": f"Path is not a directory: {path_str}"
        }

    try:
        entries = []
        for item in path.iterdir():
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": stat.st_mtime
                })
            except OSError:
                # Skip items we can't stat
                continue

        entries.sort(key=lambda x: (x["type"] != "directory", x["name"]))

        return {
            "id": request_id,
            "status": "success",
            "data": {
                "path": path_str,
                "entries": entries,
                "count": len(entries)
            }
        }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Failed to list directory: {e}"
        }


def _handle_list_exports(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle list_exports request."""
    exports_dir = get_exports_dir()
    glob_pattern = params.get("glob", "*")

    try:
        if not exports_dir.exists():
            return {
                "id": request_id,
                "status": "success",
                "data": {
                    "exports_dir": str(exports_dir.relative_to(get_project_root())),
                    "pattern": glob_pattern,
                    "files": [],
                    "count": 0
                }
            }

        files = []
        for path in exports_dir.rglob(glob_pattern):
            if path.is_file():
                try:
                    stat = path.stat()
                    rel_path = path.relative_to(exports_dir)
                    files.append({
                        "path": str(rel_path),
                        "full_path": str(path.relative_to(get_project_root())),
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
                except OSError:
                    continue

        files.sort(key=lambda x: x["path"])

        return {
            "id": request_id,
            "status": "success",
            "data": {
                "exports_dir": str(exports_dir.relative_to(get_project_root())),
                "pattern": glob_pattern,
                "files": files,
                "count": len(files)
            }
        }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Failed to list exports: {e}"
        }


def _handle_get_capabilities(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_capabilities request."""
    # Import capabilities functionality
    try:
        from ..services.manifest import generate_capabilities_json
        import tempfile
        import json

        # Generate capabilities to a temp file and read the result
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            generate_capabilities_json(temp_path)
            capabilities = json.loads(temp_path.read_text())
        finally:
            temp_path.unlink(missing_ok=True)

        return {
            "id": request_id,
            "status": "success",
            "data": capabilities
        }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Failed to generate capabilities: {e}"
        }


def _handle_expand_context(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle expand_context request."""
    # Import context command functionality
    try:
        from .context import _handle_export

        # Create mock args from params
        class MockArgs:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        args = MockArgs(
            build=params.get("build", "build"),
            preset=params.get("preset"),
            preview=params.get("preview", False),
            deep=params.get("deep", False)
        )

        # Capture stdout during execution
        import io
        old_stdout = sys.stdout
        captured_output = io.StringIO()

        try:
            sys.stdout = captured_output
            exit_code = _handle_export(args)
            stdout_content = captured_output.getvalue()
        finally:
            sys.stdout = old_stdout

        if exit_code != 0:
            return {
                "id": request_id,
                "status": "error",
                "error": f"Context export failed with exit code {exit_code}"
            }

        # Read the generated context.json
        context_path = get_exports_dir() / "context.json"
        if context_path.exists():
            context_data = json.loads(context_path.read_text())
        else:
            context_data = None

        return {
            "id": request_id,
            "status": "success",
            "data": {
                "context": context_data,
                "stdout": stdout_content.strip(),
                "exit_code": exit_code
            }
        }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": f"Failed to expand context: {e}"
        }


class MCPServer:
    """Simple MCP (Model Context Protocol) server over stdio."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.request_id = 0

    def run(self) -> int:
        """Run the MCP server loop."""
        try:
            # Send initialize response
            self._send_message({
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "list_tools": True,
                            "call_tool": True
                        }
                    },
                    "serverInfo": {
                        "name": "llmtk",
                        "version": "1.0.0"
                    }
                },
                "id": None
            })

            # Process messages
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    message = json.loads(line)
                    response = self._handle_message(message)
                    if response:
                        self._send_message(response)
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        },
                        "id": message.get("id") if "message" in locals() else None
                    }
                    self._send_message(error_response)

            return 0
        except Exception as e:
            print(f"MCP server error: {e}", file=sys.stderr)
            return 1

    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a JSON-RPC message to stdout."""
        json.dump(message, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()

    def _handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle an incoming MCP message."""
        method = message.get("method")
        message_id = message.get("id")
        params = message.get("params", {})

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "tools": [
                        {
                            "name": "llmtk.read_file",
                            "description": "Read a file from the workspace",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "File path relative to workspace root"}
                                },
                                "required": ["path"]
                            }
                        },
                        {
                            "name": "llmtk.write_file",
                            "description": "Write content to a file in the workspace",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "File path relative to workspace root"},
                                    "content": {"type": "string", "description": "File content"}
                                },
                                "required": ["path", "content"]
                            }
                        },
                        {
                            "name": "llmtk.list_directory",
                            "description": "List contents of a directory",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "Directory path relative to workspace root"}
                                },
                                "required": ["path"]
                            }
                        },
                        {
                            "name": "llmtk.list_exports",
                            "description": "List files in the exports directory",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "glob": {"type": "string", "description": "Glob pattern to filter files"}
                                }
                            }
                        },
                        {
                            "name": "llmtk.expand_context",
                            "description": "Export project context for LLM consumption",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "deep": {"type": "boolean", "description": "Generate deep context with target metadata"},
                                    "build": {"type": "string", "description": "Build directory to use"},
                                    "preset": {"type": "string", "description": "CMake preset to use"},
                                    "preview": {"type": "boolean", "description": "Preview actions without executing"}
                                }
                            }
                        },
                        {
                            "name": "llmtk.get_capabilities",
                            "description": "Get toolkit capabilities summary",
                            "inputSchema": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    ]
                },
                "id": message_id
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            # Map MCP tool names to internal request kinds
            tool_mapping = {
                "llmtk.read_file": "read_file",
                "llmtk.write_file": "write_file",
                "llmtk.list_directory": "list_directory",
                "llmtk.list_exports": "list_exports",
                "llmtk.expand_context": "expand_context",
                "llmtk.get_capabilities": "get_capabilities"
            }

            if tool_name not in tool_mapping:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": f"Unknown tool: {tool_name}"
                    },
                    "id": message_id
                }

            # Process the request
            request = {
                "id": str(self.request_id),
                "kind": tool_mapping[tool_name],
                "params": arguments
            }
            self.request_id += 1

            result = _process_single_request(request)

            if result.get("status") == "error":
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Tool execution failed",
                        "data": result.get("error")
                    },
                    "id": message_id
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result.get("data"), indent=2)
                            }
                        ]
                    },
                    "id": message_id
                }

        # For other methods, return None (no response needed)
        return None