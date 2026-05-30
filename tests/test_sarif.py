"""SARIF pipeline tests for modules/sarif_converter.py and modules/sarif_merge.py.

Migrated from the former root-level test_sarif_functionality.py (a print-style
script that `unittest discover` never collected) into the suite as real
assertions. These back the `llmtk analyze --sarif` output path.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES = REPO_ROOT / "modules"


class SarifConverterTests(unittest.TestCase):
    def test_converts_analyzer_reports_to_sarif(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "clang-tidy.json").write_text(json.dumps({
                "tool": "clang-tidy", "ok": True,
                "diagnostics": [{
                    "file": "test.cpp", "line": 10, "column": 5, "severity": "warning",
                    "message": "Use nullptr instead of NULL", "check": "modernize-use-nullptr",
                }],
                "fixes": [], "meta": {"version": "clang-tidy version 14.0.0"},
            }))
            (tmp / "cppcheck.json").write_text(json.dumps({
                "tool": "cppcheck", "ok": True,
                "issues": [{
                    "id": "nullPointer", "severity": "error", "message": "Null pointer dereference",
                    "locations": [{"file": "test.cpp", "line": 15, "column": 8}],
                }],
                "meta": {"version": "Cppcheck 2.9"},
            }))
            (tmp / "iwyu.json").write_text(json.dumps({
                "tool": "include-what-you-use", "ok": True,
                "issues": [{
                    "file": "test.cpp", "suggest_add": ["#include <memory>"],
                    "suggest_remove": ["#include <cstddef>"],
                }],
                "meta": {"version": "include-what-you-use 0.18"},
            }))

            out = tmp / "analysis.sarif"
            result = subprocess.run(
                [sys.executable, str(MODULES / "sarif_converter.py"), str(out),
                 str(tmp / "clang-tidy.json"), str(tmp / "cppcheck.json"), str(tmp / "iwyu.json")],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists())

            doc = json.loads(out.read_text())
            self.assertEqual(doc.get("version"), "2.1.0")
            runs = doc.get("runs", [])
            self.assertTrue(runs, "expected at least one SARIF run")
            total_results = sum(len(run.get("results", [])) for run in runs)
            self.assertGreater(total_results, 0)


class SarifMergeTests(unittest.TestCase):
    def test_merges_multiple_sarif_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "s1.json").write_text(json.dumps({
                "version": "2.1.0",
                "runs": [{"tool": {"driver": {"name": "tool1"}},
                          "results": [{"ruleId": "rule1", "message": {"text": "Issue 1"}, "level": "warning"}]}],
            }))
            (tmp / "s2.json").write_text(json.dumps({
                "version": "2.1.0",
                "runs": [{"tool": {"driver": {"name": "tool2"}},
                          "results": [{"ruleId": "rule2", "message": {"text": "Issue 2"}, "level": "error"}]}],
            }))

            out = tmp / "merged.sarif"
            result = subprocess.run(
                [sys.executable, str(MODULES / "sarif_merge.py"), str(out),
                 str(tmp / "s1.json"), str(tmp / "s2.json")],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists())

            doc = json.loads(out.read_text())
            runs = doc.get("runs", [])
            self.assertEqual(len(runs), 1, "merge should collapse to a single run")
            self.assertEqual(len(runs[0].get("results", [])), 2)


if __name__ == "__main__":
    unittest.main()
