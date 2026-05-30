"""End-to-end MCP stdio-loop coverage for `llmtk agent mcp`.

Unlike tests/test_agent_*.py (which call the message handler directly), this
spawns the real `cli/llmtk agent mcp` subprocess, drives it over stdin with
newline-delimited JSON-RPC, and asserts stdout carries only valid JSON-RPC
messages — no console/log pollution. A timeout guards against hangs.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "llmtk"
TIMEOUT_SECONDS = 60


def _drive_mcp(requests):
    """Run `agent mcp`, feed JSON-RPC requests, return (parsed_messages, stdout, stderr).

    Each request is a dict (or a raw string for malformed input). stdin is closed
    after the last request, so the server's read loop hits EOF and exits.
    """
    lines = []
    for req in requests:
        lines.append(req if isinstance(req, str) else json.dumps(req))
    payload = "\n".join(lines) + "\n"

    with tempfile.TemporaryDirectory() as cwd:
        proc = subprocess.Popen(
            [sys.executable, str(CLI), "agent", "mcp"],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, err = proc.communicate(input=payload, timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise AssertionError("`llmtk agent mcp` did not exit after stdin closed")

    messages = []
    for line in out.splitlines():
        if not line.strip():
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"non-JSON line on MCP stdout (console pollution): {line!r}") from exc
    return messages, out, err


class McpStdioLoopTests(unittest.TestCase):
    def test_initialize_list_call_and_error_over_stdio(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            # Notification (no id) — handshake step that must produce no response.
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "llmtk.capabilities", "arguments": {}}},
            # Malformed line — must be skipped silently, not crash the loop.
            "this-is-not-json {{{",
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "llmtk.unknown_tool", "arguments": {}}},
        ]
        messages, out, err = _drive_mcp(requests)

        # Every stdout line is valid JSON-RPC; the notification and the malformed
        # line produce no output, so exactly the four id-bearing requests reply.
        self.assertEqual(len(messages), 4, f"stdout: {out!r}\nstderr: {err!r}")
        for msg in messages:
            self.assertEqual(msg.get("jsonrpc"), "2.0")
        by_id = {msg.get("id"): msg for msg in messages}
        self.assertEqual(set(by_id), {1, 2, 3, 4})

        # 1) initialize
        init = by_id[1]["result"]
        self.assertEqual(init["serverInfo"]["name"], "llmtk")
        self.assertIn("protocolVersion", init)

        # 2) tools/list advertises the stable tools + the workflow tool
        tools = {t["name"] for t in by_id[2]["result"]["tools"]}
        self.assertIn("llmtk.capabilities", tools)
        self.assertIn("llmtk.agent_prepare", tools)

        # 3) tools/call for a JSON-safe tool returns capabilities JSON
        caps = json.loads(by_id[3]["result"]["content"][0]["text"])
        self.assertEqual(caps["schema_version"], 1)
        self.assertIn("preflight", caps["commands"])

        # 4) unknown tool -> JSON-RPC error, not a crash
        self.assertIn("error", by_id[4])
        self.assertEqual(by_id[4]["error"]["code"], -32601)

    def test_stdout_has_no_pollution_when_stdin_is_empty(self):
        # No requests: the loop should exit cleanly on EOF and print nothing.
        messages, out, err = _drive_mcp([])
        self.assertEqual(messages, [])
        self.assertEqual(out.strip(), "")


if __name__ == "__main__":
    unittest.main()
