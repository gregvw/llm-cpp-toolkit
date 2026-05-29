"""Message-handler tests for the llmtk.agent_prepare MCP workflow tool.

agent_prepare orchestrates existing stable commands (capabilities, doctor,
context export, preflight, optional CTest, list_exports) and returns a compact
envelope. These drive the MCP message handler and the agent-request dispatch
directly; full stdio-loop coverage is a separate follow-up.
"""

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

from llmtk.commands.agent import MCPServer, _process_single_request
from llmtk.core import context as ctx

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "cmake_min"
_CLANG20_BIN = Path("/opt/homebrew/opt/llvm@20/bin")


def _preferred_compilers():
    cxx, cc = _CLANG20_BIN / "clang++", _CLANG20_BIN / "clang"
    if cxx.exists() and cc.exists():
        return str(cc), str(cxx)
    return None, None


def _have_cxx():
    if _preferred_compilers()[1]:
        return True
    return any(shutil.which(name) for name in ("c++", "clang++", "g++"))


TOOLCHAIN_AVAILABLE = (
    bool(shutil.which("cmake")) and bool(shutil.which("ninja")) and _have_cxx()
)
REQUIRES_TOOLCHAIN = unittest.skipUnless(
    TOOLCHAIN_AVAILABLE, "requires cmake, ninja, and a C++ compiler"
)


@contextlib.contextmanager
def sandbox(copy_fixture=False):
    tmp = Path(tempfile.mkdtemp(prefix="llmtk-prep-"))
    if copy_fixture:
        shutil.copytree(FIXTURE, tmp, dirs_exist_ok=True)
    saved_cwd = os.getcwd()
    saved_root, saved_exports = ctx.PROJECT_ROOT, ctx.EXPORTS
    saved_cc, saved_cxx = os.environ.get("CC"), os.environ.get("CXX")
    try:
        os.chdir(tmp)
        ctx.PROJECT_ROOT = tmp.resolve()
        ctx.EXPORTS = tmp.resolve() / "exports"
        cc, cxx = _preferred_compilers()
        if cc and cxx:
            os.environ["CC"], os.environ["CXX"] = cc, cxx
        yield tmp.resolve()
    finally:
        os.chdir(saved_cwd)
        ctx.PROJECT_ROOT, ctx.EXPORTS = saved_root, saved_exports
        for key, value in (("CC", saved_cc), ("CXX", saved_cxx)):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)


def _prepare_via_mcp(arguments):
    server = MCPServer()
    resp = server._handle_message({
        "jsonrpc": "2.0", "id": 7, "method": "tools/call",
        "params": {"name": "llmtk.agent_prepare", "arguments": arguments},
    })
    assert "result" in resp, resp
    return json.loads(resp["result"]["content"][0]["text"])


def _prepare_via_request(params):
    result = _process_single_request({"id": "1", "kind": "agent_prepare", "params": params})
    assert result["status"] == "success", result
    return result["data"]


class AgentPrepareToolListTests(unittest.TestCase):
    def test_agent_prepare_is_advertised(self):
        server = MCPServer()
        resp = server._handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = {tool["name"] for tool in resp["result"]["tools"]}
        self.assertIn("llmtk.agent_prepare", names)


class AgentPrepareEnvelopeTests(unittest.TestCase):
    def test_envelope_shape_and_core_steps(self):
        with sandbox() as work:
            (work / "good.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            data = _prepare_via_mcp({"paths": ["good.cpp"], "no_syntax": True})

            self.assertIn(data["status"], {"ok", "warnings", "error"})
            for key in ("capabilities", "doctor", "context_export", "preflight", "test", "list_exports"):
                self.assertIn(key, data["steps"])
            # Commands that never need a toolchain always succeed.
            self.assertTrue(data["steps"]["capabilities"]["ok"])
            self.assertIn("ok", data["steps"]["doctor"])
            self.assertEqual(data["steps"]["preflight"]["errors"], 0)
            self.assertEqual(data["steps"]["test"]["mode"], "skip")
            # Envelope fields are the documented compact contract.
            for field in ("status", "steps", "artifacts", "warnings", "next_actions"):
                self.assertIn(field, data)
            self.assertIsInstance(data["artifacts"], list)
            self.assertIsInstance(data["warnings"], list)
            self.assertIsInstance(data["next_actions"], list)
            # Always-written artifacts are inventoried (project-root relative).
            self.assertIn("exports/capabilities.json", data["artifacts"])
            self.assertIn("exports/doctor.json", data["artifacts"])

    def test_preflight_errors_become_warnings_and_next_actions(self):
        with sandbox() as work:
            (work / "bad.cpp").write_text(
                "int main() {\n    int v[] = {1, 2, 3;\n    return 0;\n}\n", encoding="utf-8"
            )
            data = _prepare_via_mcp({"paths": ["bad.cpp"], "no_syntax": True})
            self.assertGreaterEqual(data["steps"]["preflight"]["errors"], 1)
            self.assertFalse(data["steps"]["preflight"]["ok"])
            self.assertEqual(data["status"], "warnings")
            self.assertTrue(any("preflight" in w for w in data["warnings"]))
            self.assertTrue(any("preflight" in a.lower() for a in data["next_actions"]))

    def test_agent_request_dispatch_returns_same_envelope(self):
        with sandbox() as work:
            (work / "good.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            data = _prepare_via_request({"paths": ["good.cpp"], "no_syntax": True})
            self.assertIn("status", data)
            self.assertIn("steps", data)
            self.assertTrue(data["steps"]["capabilities"]["ok"])


class AgentPrepareFullTests(unittest.TestCase):
    @REQUIRES_TOOLCHAIN
    def test_full_prepare_on_fixture(self):
        with sandbox(copy_fixture=True):
            data = _prepare_via_mcp({"no_syntax": True, "tests": "preview"})

            self.assertIn(data["status"], {"ok", "warnings"})
            self.assertTrue(data["steps"]["context_export"]["ok"])
            self.assertTrue(
                str(data["steps"]["context_export"]["compile_commands"]).endswith("compile_commands.json")
            )
            self.assertIn("exports/context.json", data["artifacts"])
            self.assertIn("exports/capabilities.json", data["artifacts"])
            # Preview lists the fixture's CTest cases without running them.
            self.assertEqual(data["steps"]["test"]["mode"], "preview")
            self.assertGreaterEqual(data["steps"]["test"]["stats"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
