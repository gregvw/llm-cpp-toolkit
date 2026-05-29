"""Agent command for llmtk - JSON request handler and MCP server."""

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.context import get_exports_dir, get_modules_dir, get_project_root
from ..core.dry_run import is_dry_run
from ..core.utils import get_version


# Preflight exit codes that represent a successful run: 0 (clean), 2 (warnings),
# 3 (errors found). Higher codes (e.g. 10) indicate the tool itself failed.
PREFLIGHT_SUCCESS_CODES = {0, 2, 3}


MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "llmtk.context_export",
        "description": "Export C++/CMake project context into exports/context.json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deep": {"type": "boolean", "description": "Include target, preset, cache, and toolchain metadata"},
                "build": {"type": "string", "description": "Build directory to use"},
                "preset": {"type": "string", "description": "CMake configure preset to use"},
                "preview": {"type": "boolean", "description": "Preview actions without executing"},
            },
        },
    },
    {
        "name": "llmtk.preflight",
        "description": "Run fast syntax/config checks and write exports/reports/preflight.json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff": {"type": "string", "description": "Git base ref or BASE...TARGET range"},
                "since": {"type": "string", "description": "Git ref for changed files"},
                "paths": {"type": "array", "items": {"type": "string"}, "description": "Explicit paths to check"},
                "extensions": {"type": "array", "items": {"type": "string"}, "description": "Extension filter"},
                "strict": {"type": "boolean", "description": "Treat warnings as errors"},
                "json": {"type": "string", "description": "JSON output path"},
                "sarif": {"type": "string", "description": "SARIF output path"},
            },
        },
    },
    {
        "name": "llmtk.diagnostics",
        "description": "Thin compiler stderr into structured diagnostics JSON",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log": {"type": "string", "description": "Path to stderr log"},
                "text": {"type": "string", "description": "Raw stderr text"},
                "level": {"type": "string", "enum": ["summary", "focused", "detailed"]},
                "context_budget": {"type": "integer", "description": "Maximum characters in text highlights"},
                "json": {"type": "string", "description": "JSON output path"},
                "text_output": {"type": "string", "description": "Text output path"},
                "sarif": {"type": "string", "description": "SARIF output path"},
            },
        },
    },
    {
        "name": "llmtk.test",
        "description": "Run CTest and write structured JSON/SARIF test exports",
        "inputSchema": {
            "type": "object",
            "properties": {
                "build_dir": {"type": "string", "description": "CMake build directory"},
                "regex": {"type": "string", "description": "CTest -R filter"},
                "exclude": {"type": "string", "description": "CTest -E filter"},
                "label": {"type": "string", "description": "CTest -L filter"},
                "parallel": {"type": "integer", "description": "Parallel test jobs"},
                "timeout": {"type": "integer", "description": "Per-test timeout in seconds"},
                "rerun_failed": {"type": "boolean", "description": "Use ctest --rerun-failed"},
                "preview": {"type": "boolean", "description": "List tests without running them"},
                "json": {"type": "string", "description": "JSON output path"},
                "sarif": {"type": "string", "description": "SARIF output path"},
            },
        },
    },
    {
        "name": "llmtk.deps",
        "description": "Export CMake target dependency graph JSON",
        "inputSchema": {
            "type": "object",
            "properties": {
                "build_dir": {"type": "string", "description": "CMake build directory"},
                "output_dir": {"type": "string", "description": "Dependency graph output directory"},
                "graphviz": {"type": "boolean", "description": "Also write Graphviz DOT output"},
                "symbols": {"type": "boolean", "description": "Include symbol-level analysis when available"},
            },
        },
    },
    {
        "name": "llmtk.capabilities",
        "description": "Return stable llmtk command/tool capabilities from the manifests",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "llmtk.list_exports",
        "description": "List generated artifacts under exports/",
        "inputSchema": {
            "type": "object",
            "properties": {
                "glob": {"type": "string", "description": "Glob pattern to filter exports"},
            },
        },
    },
    {
        "name": "llmtk.agent_prepare",
        "description": (
            "Prepare a C++ workspace for an agent in one call: runs capabilities, "
            "doctor, context export, and preflight (plus an optional CTest step), "
            "then returns compact JSON with status, artifact paths, warnings, and "
            "recommended next actions. Orchestrates existing stable commands only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "build": {"type": "string", "description": "CMake build directory (default: build)"},
                "preset": {"type": "string", "description": "CMake configure preset for context export"},
                "deep": {"type": "boolean", "description": "Use deep context export"},
                "paths": {"type": "array", "items": {"type": "string"}, "description": "Explicit paths for preflight"},
                "diff": {"type": "string", "description": "Git base ref for preflight discovery"},
                "since": {"type": "string", "description": "Git ref for preflight discovery"},
                "strict": {"type": "boolean", "description": "Treat preflight warnings as errors"},
                "no_syntax": {"type": "boolean", "description": "Disable preflight external syntax probes"},
                "tests": {
                    "type": "string",
                    "enum": ["skip", "preview", "run"],
                    "description": "Optional CTest step (default: skip)",
                },
            },
        },
    },
]


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
        elif kind in {"expand_context", "context_export"}:
            return _handle_expand_context(request_id, params)
        elif kind == "preflight":
            return _handle_preflight(request_id, params)
        elif kind == "diagnostics":
            return _handle_diagnostics(request_id, params)
        elif kind == "test":
            return _handle_test(request_id, params)
        elif kind == "deps":
            return _handle_deps(request_id, params)
        elif kind == "agent_prepare":
            return _handle_agent_prepare(request_id, params)
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


def _handle_preflight(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle preflight request."""
    try:
        from .preflight import run_preflight_for_agent, default_json_path

        stdout_content, stderr_content, exit_code = _capture_command(run_preflight_for_agent, params)
        json_path = Path(params.get("json") or default_json_path())
        return _artifact_response(
            request_id,
            exit_code,
            json_path,
            stdout_content,
            stderr_content,
            "preflight",
            # Exit 2 (warnings) and 3 (errors) mean the run succeeded and found
            # issues — surface the findings rather than reporting a tool failure.
            success_exit_codes=PREFLIGHT_SUCCESS_CODES,
        )
    except Exception as e:
        return {"id": request_id, "status": "error", "error": f"Failed to run preflight: {e}"}


def _handle_test(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle test request."""
    try:
        from .test import run_test_for_agent

        stdout_content, stderr_content, exit_code = _capture_command(run_test_for_agent, params)
        json_path = Path(params.get("json") or get_exports_dir() / "tests" / "ctest_results.json")
        return _artifact_response(
            request_id,
            exit_code,
            json_path,
            stdout_content,
            stderr_content,
            "test",
            allow_nonzero=True,
        )
    except Exception as e:
        return {"id": request_id, "status": "error", "error": f"Failed to run tests: {e}"}


def _handle_deps(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle dependency graph request."""
    try:
        from .deps import run_deps_for_agent

        stdout_content, stderr_content, exit_code = _capture_command(run_deps_for_agent, params)
        output_dir = Path(params.get("output_dir") or "exports/dependency_graphs")
        json_path = output_dir / "dependencies.json"
        return _artifact_response(
            request_id,
            exit_code,
            json_path,
            stdout_content,
            stderr_content,
            "deps",
        )
    except Exception as e:
        return {"id": request_id, "status": "error", "error": f"Failed to export dependency graph: {e}"}


def _handle_diagnostics(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stderr thinning request."""
    log = params.get("log")
    stderr_text = params.get("text")
    if not log and stderr_text is None:
        return {
            "id": request_id,
            "status": "error",
            "error": "Provide either 'log' or 'text' for diagnostics",
        }

    diagnostics_dir = get_exports_dir() / "diagnostics"
    json_path = Path(params.get("json") or diagnostics_dir / "stderr-thin.json")
    text_path = Path(params.get("text_output") or diagnostics_dir / "stderr-thin.txt")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(get_modules_dir() / "stderr_thin.py"),
        "--level",
        str(params.get("level", "focused")),
        "--context-budget",
        str(params.get("context_budget", 8000)),
        "--json",
        str(json_path),
        "--text",
        str(text_path),
    ]
    if params.get("sarif"):
        cmd.extend(["--sarif", str(params["sarif"])])
    if log:
        safe_log = _safe_path(str(log))
        if not safe_log:
            return {"id": request_id, "status": "error", "error": f"Invalid or unsafe path: {log}"}
        cmd.extend(["--log", str(safe_log)])

    result = subprocess.run(
        cmd,
        cwd=get_project_root(),
        input=None if log else str(stderr_text),
        capture_output=True,
        text=True,
        check=False,
    )
    return _artifact_response(
        request_id,
        result.returncode,
        json_path,
        result.stdout,
        result.stderr,
        "diagnostics",
    )


@contextlib.contextmanager
def _suppress_console():
    """Discard stdout/stderr (including subprocess fds) for the duration.

    Orchestration runs commands that print to stdout and spawn cmake/ctest;
    suppressing at the fd level keeps that noise out of the JSON-RPC stream.
    Results are read back from the on-disk artifacts afterward.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_out, saved_err = os.dup(1), os.dup(2)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        for fd in (devnull, saved_out, saved_err):
            os.close(fd)


def _rel(path: Path) -> str:
    """Express a path relative to the project root when possible."""
    try:
        return str(Path(path).resolve().relative_to(get_project_root().resolve()))
    except (ValueError, OSError):
        return str(path)


def _handle_agent_prepare(request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrate stable commands to prepare a workspace for an agent.

    Runs capabilities, doctor, context export, and preflight (plus an optional
    CTest step), then returns a compact summary: an overall status, per-step
    results with artifact paths, collected warnings, and recommended next
    actions. It only composes existing stable commands; it adds no new CLI
    surface and does not template any JSON output.
    """
    steps: Dict[str, Any] = {}
    warnings: List[str] = []
    next_actions: List[str] = []
    errored: List[str] = []
    exports_dir = get_exports_dir()

    with _suppress_console():
        # 1) capabilities
        try:
            from ..services.manifest import generate_capabilities_json

            caps_path = exports_dir / "capabilities.json"
            generate_capabilities_json(caps_path)
            caps = _read_json_artifact(caps_path) or {}
            steps["capabilities"] = {
                "ok": True,
                "artifact": _rel(caps_path),
                "commands": sorted((caps.get("commands") or {}).keys()),
            }
        except Exception as exc:  # noqa: BLE001
            steps["capabilities"] = {"ok": False, "error": str(exc)}
            errored.append("capabilities")

        # 2) doctor
        try:
            from .doctor import cmd_doctor

            cmd_doctor(argparse.Namespace(_from_install=True, cmake=False))
            doctor_path = exports_dir / "doctor.json"
            summary = (_read_json_artifact(doctor_path) or {}).get("_summary", {})
            missing_core = summary.get("missing_core") or []
            steps["doctor"] = {
                "ok": not missing_core,
                "artifact": _rel(doctor_path),
                "found": summary.get("found"),
                "missing_core": missing_core,
            }
            if missing_core:
                warnings.append(f"doctor: missing core tools: {', '.join(missing_core)}")
                next_actions.append("Run `llmtk install` to install missing core tools")
        except Exception as exc:  # noqa: BLE001
            steps["doctor"] = {"ok": False, "error": str(exc)}
            errored.append("doctor")

        # 3) context export
        try:
            from .context import _handle_export

            rc = _handle_export(argparse.Namespace(
                build=params.get("build", "build"),
                preset=params.get("preset"),
                preview=False,
                deep=bool(params.get("deep", False)),
            ))
            ctx_path = exports_dir / "context.json"
            ctx_data = _read_json_artifact(ctx_path) or {}
            ok = rc == 0
            steps["context_export"] = {
                "ok": ok,
                "artifact": _rel(ctx_path),
                "compile_commands": ctx_data.get("compile_commands"),
            }
            if not ok:
                warnings.append("context export failed; the build could not be configured")
                next_actions.append(
                    "Ensure cmake and a generator (e.g. Ninja) are installed and the project configures"
                )
            for note in ctx_data.get("_warnings", []) or []:
                warnings.append(f"context: {note}")
        except Exception as exc:  # noqa: BLE001
            steps["context_export"] = {"ok": False, "error": str(exc)}
            warnings.append(f"context export error: {exc}")

        # 4) preflight
        try:
            from .preflight import default_json_path, run_preflight_for_agent

            pf_params = {
                k: params[k]
                for k in ("diff", "since", "paths", "extensions", "strict", "no_syntax", "json")
                if k in params
            }
            rc = run_preflight_for_agent(pf_params)
            pf_path = Path(pf_params.get("json") or default_json_path())
            pf_summary = (_read_json_artifact(pf_path) or {}).get("summary", {})
            errors = int(pf_summary.get("errors", 0) or 0)
            pf_warns = int(pf_summary.get("warnings", 0) or 0)
            steps["preflight"] = {
                "ok": errors == 0 and rc != 10,
                "artifact": _rel(pf_path),
                "errors": errors,
                "warnings": pf_warns,
            }
            if rc == 10:
                warnings.append("preflight failed to run")
                errored.append("preflight")
            elif errors:
                warnings.append(f"preflight: {errors} error(s)")
                next_actions.append("Resolve preflight errors before building")
            elif pf_warns:
                warnings.append(f"preflight: {pf_warns} warning(s)")
        except Exception as exc:  # noqa: BLE001
            steps["preflight"] = {"ok": False, "error": str(exc)}
            errored.append("preflight")

        # 5) optional CTest step
        tests_mode = str(params.get("tests", "skip"))
        if tests_mode in ("preview", "run"):
            try:
                from .test import run_test_for_agent

                rc = run_test_for_agent({
                    "build_dir": params.get("build", "build"),
                    "preview": tests_mode == "preview",
                })
                stats = (_read_json_artifact(exports_dir / "tests" / "ctest_results.json") or {}).get("stats", {})
                steps["test"] = {
                    "mode": tests_mode,
                    "ok": rc == 0,
                    "artifact": _rel(exports_dir / "tests" / "ctest_results.json"),
                    "stats": {k: stats.get(k) for k in ("total", "passed", "failed")},
                }
                failed = int(stats.get("failed", 0) or 0)
                if tests_mode == "run" and failed:
                    warnings.append(f"tests: {failed} failing")
                    next_actions.append("Investigate failing tests")
            except Exception as exc:  # noqa: BLE001
                steps["test"] = {"ok": False, "error": str(exc)}
                warnings.append(f"test error: {exc}")
        else:
            steps["test"] = {"mode": "skip"}

        # 6) list exports (single source of truth for the artifact inventory)
        artifacts: List[str] = []
        try:
            listing = _handle_list_exports(request_id, {})
            if listing.get("status") == "success":
                for entry in listing["data"].get("files", []):
                    full = entry.get("full_path")
                    if full:
                        artifacts.append(full)
            steps["list_exports"] = {"ok": True, "count": len(artifacts)}
        except Exception as exc:  # noqa: BLE001
            steps["list_exports"] = {"ok": False, "error": str(exc)}

    if errored:
        status = "error"
    elif warnings:
        status = "warnings"
    else:
        status = "ok"
    if status == "ok":
        next_actions.append("Workspace is ready; proceed with builds or edits")

    return {
        "id": request_id,
        "status": "success",
        "data": {
            "status": status,
            "steps": steps,
            "artifacts": sorted(artifacts),
            "warnings": warnings,
            "next_actions": next_actions,
        },
    }


def _capture_command(func: Any, params: Dict[str, Any]) -> tuple[str, str, int]:
    """Run a command handler while capturing stdout/stderr for agent responses."""
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        exit_code = func(params)
    return stdout_buffer.getvalue().strip(), stderr_buffer.getvalue().strip(), int(exit_code or 0)


def _artifact_response(
    request_id: str,
    exit_code: int,
    json_path: Path,
    stdout_content: str,
    stderr_content: str,
    operation: str,
    *,
    allow_nonzero: bool = False,
    success_exit_codes: Optional[set] = None,
) -> Dict[str, Any]:
    """Build a standard response around a JSON artifact.

    A run is treated as successful when its exit code is 0, when
    ``allow_nonzero`` is set (any code is fine, e.g. ctest with failing tests),
    or when the code is listed in ``success_exit_codes`` (e.g. preflight codes
    that mean "ran fine, found issues"). Anything else is a tool failure.
    """
    data = _read_json_artifact(json_path)
    if success_exit_codes is not None:
        succeeded = exit_code in success_exit_codes
    else:
        succeeded = allow_nonzero or exit_code == 0
    if not succeeded:
        return {
            "id": request_id,
            "status": "error",
            "error": f"{operation} failed with exit code {exit_code}",
            "data": {
                "artifact": str(json_path),
                "json": data,
                "stdout": stdout_content,
                "stderr": stderr_content,
                "exit_code": exit_code,
            },
        }
    return {
        "id": request_id,
        "status": "success",
        "data": {
            "artifact": str(json_path),
            "json": data,
            "stdout": stdout_content,
            "stderr": stderr_content,
            "exit_code": exit_code,
        },
    }


def _read_json_artifact(path: Path) -> Optional[Dict[str, Any]]:
    """Read a JSON artifact when it exists and is parseable."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


class MCPServer:
    """Simple MCP (Model Context Protocol) server over stdio."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.request_id = 0

    def run(self) -> int:
        """Run the MCP server loop."""
        try:
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

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "llmtk", "version": get_version()},
                },
                "id": message_id,
            }

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "result": {"tools": MCP_TOOLS},
                "id": message_id
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            # Map MCP tool names to internal request kinds
            tool_mapping = {
                "llmtk.context_export": "context_export",
                "llmtk.preflight": "preflight",
                "llmtk.diagnostics": "diagnostics",
                "llmtk.test": "test",
                "llmtk.deps": "deps",
                "llmtk.capabilities": "get_capabilities",
                "llmtk.agent_prepare": "agent_prepare",
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
