"""Integration tests for the stable llmtk agent backend.

These exercise the supported commands (context export, preflight, test, deps)
against a minimal CMake fixture, plus the MCP surface (initialize, tools/list,
tools/call). Commands that require a real CMake configure are skipped when a
C++ toolchain is unavailable so the suite still runs on minimal CI.

The tests run each command inside a throwaway copy of the fixture with the
toolkit's project-root/exports globals repointed at it, so nothing is written
into the repository tree.
"""

import argparse
import contextlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llmtk.core import context as ctx
from llmtk.commands import context as context_cmd
from llmtk.commands import deps as deps_cmd
from llmtk.commands import preflight as preflight_cmd
from llmtk.commands import test as test_cmd
from llmtk.commands.agent import MCPServer

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "cmake_min"

# Per project preference, build/configure C++ with Homebrew clang 20 when present
# (falling back to whatever the platform provides so other machines still work).
_CLANG20_BIN = Path("/opt/homebrew/opt/llvm@20/bin")

# A throwaway translation unit with an unbalanced delimiter — the known-bad
# preflight input. Generated at test time so no broken source lives in the repo.
BAD_SOURCE = (
    "#include <iostream>\n"
    "int main() {\n"
    "    int values[] = {1, 2, 3;\n"
    "    return 0;\n"
    "}\n"
)


def _preferred_compilers():
    """Return (CC, CXX) paths to prefer, or (None, None) to use platform defaults."""
    cxx = _CLANG20_BIN / "clang++"
    cc = _CLANG20_BIN / "clang"
    if cxx.exists() and cc.exists():
        return str(cc), str(cxx)
    return None, None


def _have_cxx():
    cc, cxx = _preferred_compilers()
    if cxx:
        return True
    return any(shutil.which(name) for name in ("c++", "clang++", "g++"))


# `context export` configures with `-G Ninja`, so the cmake-dependent tests need
# cmake, Ninja, and a C++ compiler all present.
TOOLCHAIN_AVAILABLE = (
    bool(shutil.which("cmake")) and bool(shutil.which("ninja")) and _have_cxx()
)
REQUIRES_TOOLCHAIN = unittest.skipUnless(
    TOOLCHAIN_AVAILABLE, "requires cmake, ninja, and a C++ compiler"
)


def _restore_env(name, value):
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


@contextlib.contextmanager
def _silenced():
    """Redirect stdout/stderr (including subprocess output) to /dev/null.

    Commands here shell out to cmake/ctest, which write to the inherited file
    descriptors; silencing at the fd level keeps test output readable. The
    descriptors are restored before unittest reports results, so failures are
    still printed normally.
    """
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_out, saved_err = os.dup(1), os.dup(2)
    sys.stdout.flush()
    sys.stderr.flush()
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


@contextlib.contextmanager
def sandbox(copy_fixture=False):
    """Run a block inside a temp project with toolkit globals repointed at it."""
    tmp = Path(tempfile.mkdtemp(prefix="llmtk-it-"))
    if copy_fixture:
        shutil.copytree(FIXTURE, tmp, dirs_exist_ok=True)
    saved_cwd = os.getcwd()
    saved_root = ctx.PROJECT_ROOT
    saved_exports = ctx.EXPORTS
    saved_cc = os.environ.get("CC")
    saved_cxx = os.environ.get("CXX")
    try:
        os.chdir(tmp)
        ctx.PROJECT_ROOT = tmp.resolve()
        ctx.EXPORTS = tmp.resolve() / "exports"
        cc, cxx = _preferred_compilers()
        if cc and cxx:
            os.environ["CC"] = cc
            os.environ["CXX"] = cxx
        with _silenced():
            yield tmp.resolve()
    finally:
        os.chdir(saved_cwd)
        ctx.PROJECT_ROOT = saved_root
        ctx.EXPORTS = saved_exports
        _restore_env("CC", saved_cc)
        _restore_env("CXX", saved_cxx)
        shutil.rmtree(tmp, ignore_errors=True)


def _run_context_export(deep=False, build="build"):
    args = argparse.Namespace(build=build, preset=None, preview=False, deep=deep)
    return context_cmd._handle_export(args)


def _mcp_call(server, name, arguments, message_id):
    return server._handle_message(
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


class ContextExportTests(unittest.TestCase):
    @REQUIRES_TOOLCHAIN
    def test_context_export_generates_artifacts(self):
        with sandbox(copy_fixture=True) as proj:
            self.assertEqual(_run_context_export(), 0)

            context_json = proj / "exports" / "context.json"
            self.assertTrue(context_json.exists())
            data = json.loads(context_json.read_text())

            self.assertTrue((proj / "exports" / "compile_commands.json").exists())
            self.assertTrue(str(data["compile_commands"]).endswith("compile_commands.json"))
            # File API replies were copied and at least the codemodel is present.
            files = data["cmake_file_api"]["files"]
            self.assertTrue(files)
            self.assertTrue(any(name.startswith("codemodel-") for name in files))
            self.assertIn("build_dir", data["_meta"])


class PreflightTests(unittest.TestCase):
    def test_preflight_passes_known_good(self):
        with sandbox(copy_fixture=True) as proj:
            out = proj / "exports" / "reports" / "preflight.json"
            rc = preflight_cmd.run_preflight_for_agent(
                {"paths": ["src/main.cpp"], "no_syntax": True, "json": str(out)}
            )
            self.assertEqual(rc, 0)
            summary = json.loads(out.read_text())["summary"]
            self.assertEqual(summary["errors"], 0)

    def test_preflight_flags_known_bad(self):
        with sandbox(copy_fixture=True) as proj:
            (proj / "bad.cpp").write_text(BAD_SOURCE, encoding="utf-8")
            out = proj / "exports" / "reports" / "preflight.json"
            rc = preflight_cmd.run_preflight_for_agent(
                {"paths": ["bad.cpp"], "no_syntax": True, "json": str(out)}
            )
            # Exit code 3 == errors found (a successful run that found problems).
            self.assertEqual(rc, 3)
            summary = json.loads(out.read_text())["summary"]
            self.assertGreaterEqual(summary["errors"], 1)


class DepsTests(unittest.TestCase):
    @REQUIRES_TOOLCHAIN
    def test_deps_exports_targets_from_build_dir(self):
        with sandbox(copy_fixture=True) as proj:
            # context export configures the build and populates the File API.
            self.assertEqual(_run_context_export(), 0)

            rc = deps_cmd.handle_deps(
                argparse.Namespace(
                    build_dir="build",
                    output_dir="exports/dependency_graphs",
                    json=True,
                    graphviz=False,
                    symbols=False,
                )
            )
            self.assertEqual(rc, 0)

            dep_json = proj / "exports" / "dependency_graphs" / "dependencies.json"
            self.assertTrue(dep_json.exists())
            data = json.loads(dep_json.read_text())
            self.assertTrue(data["_meta"]["codemodel_available"])
            self.assertIn("hello", data["targets"])
            self.assertEqual(data["targets"]["hello"]["type"], "EXECUTABLE")


class CTestTests(unittest.TestCase):
    @REQUIRES_TOOLCHAIN
    def test_test_json_for_passing_and_failing_cases(self):
        with sandbox(copy_fixture=True) as proj:
            self.assertEqual(_run_context_export(), 0)

            passing = proj / "exports" / "tests" / "pass.json"
            rc_pass = test_cmd.run_test_for_agent(
                {"build_dir": "build", "regex": "hello_passes", "json": str(passing)}
            )
            self.assertEqual(rc_pass, 0)
            pdata = json.loads(passing.read_text())
            self.assertEqual(pdata["stats"]["total"], 1)
            self.assertEqual(pdata["stats"]["passed"], 1)
            self.assertEqual(pdata["stats"]["failed"], 0)
            self.assertEqual(pdata["failures"], [])

            failing = proj / "exports" / "tests" / "fail.json"
            rc_fail = test_cmd.run_test_for_agent(
                {"build_dir": "build", "regex": "hello_fails", "json": str(failing)}
            )
            self.assertNotEqual(rc_fail, 0)
            fdata = json.loads(failing.read_text())
            self.assertEqual(fdata["stats"]["failed"], 1)
            self.assertEqual(fdata["failures"][0]["name"], "hello_fails")
            self.assertEqual(fdata["failures"][0]["status"], "failed")


class MCPProtocolTests(unittest.TestCase):
    def test_initialize_reports_server_info(self):
        server = MCPServer()
        resp = server._handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "llmtk")
        self.assertIn("protocolVersion", resp["result"])
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_tools_list_advertises_stable_tools(self):
        server = MCPServer()
        resp = server._handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        tools = {tool["name"] for tool in resp["result"]["tools"]}
        for expected in (
            "llmtk.context_export",
            "llmtk.preflight",
            "llmtk.diagnostics",
            "llmtk.test",
            "llmtk.deps",
            "llmtk.capabilities",
        ):
            self.assertIn(expected, tools)

    def test_tools_call_capabilities(self):
        server = MCPServer()
        resp = _mcp_call(server, "llmtk.capabilities", {}, 3)
        self.assertNotIn("error", resp)
        data = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(data["schema_version"], 1)
        self.assertIn("preflight", data["commands"])
        self.assertNotIn("bench", data["commands"])
        self.assertIn("bench", data["planned_commands"])

    def test_tools_call_preflight_returns_findings_not_error(self):
        with sandbox() as proj:
            (proj / "bad.cpp").write_text(BAD_SOURCE, encoding="utf-8")
            server = MCPServer()
            resp = _mcp_call(
                server,
                "llmtk.preflight",
                {"paths": ["bad.cpp"], "no_syntax": True},
                4,
            )
            # Findings are a successful outcome, not a JSON-RPC error.
            self.assertNotIn("error", resp)
            data = json.loads(resp["result"]["content"][0]["text"])
            self.assertEqual(data["exit_code"], 3)
            self.assertGreaterEqual(data["json"]["summary"]["errors"], 1)

    def test_tools_call_diagnostics_parses_stderr(self):
        with sandbox() as proj:
            server = MCPServer()
            stderr_text = (
                "bad.cpp:3:24: error: expected ']'\n"
                "    int values[] = {1, 2, 3;\n"
                "                       ^\n"
            )
            resp = _mcp_call(server, "llmtk.diagnostics", {"text": stderr_text}, 5)
            self.assertNotIn("error", resp)
            data = json.loads(resp["result"]["content"][0]["text"])
            self.assertEqual(data["exit_code"], 0)
            self.assertGreaterEqual(len(data["json"]["diagnostics"]), 1)


if __name__ == "__main__":
    unittest.main()
