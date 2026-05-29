"""CLI-level coverage for stable commands not exercised end-to-end elsewhere.

These drive commands through the real argument parser (create_parser ->
parse_args -> func) so registration and argument wiring are covered too, closing
gaps noted in docs/AGENT_BACKEND_TESTING.md: doctor, stderr-thin, and
context export --deep.

Each test runs inside a temp project with the toolkit's project-root/exports
globals repointed at it, so the repository tree is never touched. Tests that
need a real CMake configure are skipped without a toolchain.
"""

import contextlib
import io
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

from llmtk.cli import create_parser
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


def _run_cli(argv):
    """Drive a command through the real parser, returning its exit code."""
    parser = create_parser()
    args = parser.parse_args(argv)
    return args.func(args)


@contextlib.contextmanager
def _silenced():
    """Silence stdout/stderr (incl. subprocess output) at the fd level."""
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
    tmp = Path(tempfile.mkdtemp(prefix="llmtk-cli-"))
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


class DoctorCliTests(unittest.TestCase):
    def test_doctor_writes_structured_report(self):
        with sandbox() as work:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = _run_cli(["doctor"])
            self.assertEqual(rc, 0)

            report = json.loads((work / "exports" / "doctor.json").read_text())
            self.assertIn("generated_at", report["_meta"])
            summary = report["_summary"]
            self.assertIsInstance(summary["total_tools"], int)
            self.assertGreater(summary["total_tools"], 0)
            self.assertIsInstance(summary["found"], int)
            # Per-tool entries are present and shaped as documented.
            self.assertIn("cmake", report)
            self.assertIn("found", report["cmake"])


class StderrThinCliTests(unittest.TestCase):
    def test_stderr_thin_log_to_json(self):
        with sandbox() as work:
            log = work / "build.log"
            log.write_text(
                "main.cpp:3:24: error: expected ']'\n"
                "    int values[] = {1, 2, 3;\n"
                "                       ^\n",
                encoding="utf-8",
            )
            out = work / "diagnostics.json"  # parent (work) exists; module won't mkdir
            with _silenced():
                rc = _run_cli(
                    ["stderr-thin", "--log", str(log), "--json", str(out), "--level", "focused"]
                )
            self.assertEqual(rc, 0)

            data = json.loads(out.read_text())
            self.assertIn("_meta", data)
            self.assertGreaterEqual(len(data["diagnostics"]), 1)


class ContextExportDeepCliTests(unittest.TestCase):
    @REQUIRES_TOOLCHAIN
    def test_context_export_deep_summarizes_targets_and_toolchain(self):
        with sandbox(copy_fixture=True) as work:
            with _silenced():
                rc = _run_cli(["context", "export", "--deep"])
            self.assertEqual(rc, 0)

            data = json.loads((work / "exports" / "context.json").read_text())
            self.assertEqual(data["_meta"]["mode"], "deep")
            target_names = [t.get("name") for t in data.get("targets", [])]
            self.assertIn("hello", target_names)
            # Deep mode adds toolchain + cache summaries beyond the basic export.
            self.assertTrue(data.get("toolchains"), "expected toolchain summary")
            self.assertIn("cache", data)


if __name__ == "__main__":
    unittest.main()
