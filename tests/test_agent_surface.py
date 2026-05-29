import json
import tempfile
import unittest
from pathlib import Path

from llmtk.commands.agent import MCPServer
from llmtk.commands.test import build_ctest_summary
from llmtk.services.manifest import generate_capabilities_json


class AgentSurfaceTests(unittest.TestCase):
    def test_capabilities_only_advertises_supported_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "capabilities.json"
            generate_capabilities_json(out)
            data = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], 1)
        self.assertIn("preflight", data["commands"])
        self.assertIn("test", data["commands"])
        self.assertIn("deps", data["commands"])
        self.assertIn("bench", data["planned_commands"])
        self.assertNotIn("bench", data["commands"])

    def test_mcp_tool_list_is_workflow_focused(self) -> None:
        server = MCPServer()
        response = server._handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = {tool["name"] for tool in response["result"]["tools"]}

        self.assertIn("llmtk.context_export", tools)
        self.assertIn("llmtk.preflight", tools)
        self.assertIn("llmtk.diagnostics", tools)
        self.assertIn("llmtk.test", tools)
        self.assertIn("llmtk.deps", tools)
        self.assertNotIn("llmtk.write_file", tools)

    def test_ctest_nonzero_without_junit_is_structured(self) -> None:
        summary = build_ctest_summary(
            cmd=["ctest", "--test-dir", "build"],
            build_dir="build",
            return_code=8,
            duration_seconds=1.25,
            stdout="",
            stderr="",
            junit_path=None,
            preview=False,
        )

        self.assertEqual(summary["_meta"]["return_code"], 8)
        self.assertEqual(summary["stats"]["total"], 0)
        self.assertEqual(summary["failures"][0]["name"], "ctest")


if __name__ == "__main__":
    unittest.main()
