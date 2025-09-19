#!/usr/bin/env python3
"""Basic test for SARIF functionality in llmtk."""

import json
import tempfile
import subprocess
import sys
from pathlib import Path

def test_sarif_converter():
    """Test SARIF converter functionality."""
    print("Testing SARIF converter...")

    # Create sample analysis reports
    reports_dir = Path("test_reports")
    reports_dir.mkdir(exist_ok=True)

    # Sample clang-tidy report
    clang_tidy_report = {
        "tool": "clang-tidy",
        "ok": True,
        "diagnostics": [
            {
                "file": "test.cpp",
                "line": 10,
                "column": 5,
                "severity": "warning",
                "message": "Use nullptr instead of NULL",
                "check": "modernize-use-nullptr"
            }
        ],
        "fixes": [],
        "meta": {"version": "clang-tidy version 14.0.0"}
    }

    # Sample cppcheck report
    cppcheck_report = {
        "tool": "cppcheck",
        "ok": True,
        "issues": [
            {
                "id": "nullPointer",
                "severity": "error",
                "message": "Null pointer dereference",
                "locations": [
                    {"file": "test.cpp", "line": 15, "column": 8}
                ]
            }
        ],
        "meta": {"version": "Cppcheck 2.9"}
    }

    # Sample IWYU report
    iwyu_report = {
        "tool": "include-what-you-use",
        "ok": True,
        "issues": [
            {
                "file": "test.cpp",
                "suggest_add": ["#include <memory>"],
                "suggest_remove": ["#include <cstddef>"]
            }
        ],
        "meta": {"version": "include-what-you-use 0.18"}
    }

    # Write sample reports
    with open(reports_dir / "clang-tidy.json", "w") as f:
        json.dump(clang_tidy_report, f, indent=2)

    with open(reports_dir / "cppcheck.json", "w") as f:
        json.dump(cppcheck_report, f, indent=2)

    with open(reports_dir / "iwyu.json", "w") as f:
        json.dump(iwyu_report, f, indent=2)

    # Test SARIF converter
    sarif_converter = Path("modules/sarif_converter.py")
    if not sarif_converter.exists():
        print("❌ SARIF converter not found")
        return False

    try:
        result = subprocess.run([
            sys.executable, str(sarif_converter),
            str(reports_dir / "analysis.sarif"),
            str(reports_dir / "clang-tidy.json"),
            str(reports_dir / "cppcheck.json"),
            str(reports_dir / "iwyu.json")
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ SARIF converter failed: {result.stderr}")
            return False

        # Check if SARIF file was created
        sarif_file = reports_dir / "analysis.sarif"
        if not sarif_file.exists():
            print("❌ SARIF file was not created")
            return False

        # Validate SARIF content
        with open(sarif_file) as f:
            sarif_doc = json.load(f)

        if sarif_doc.get("version") != "2.1.0":
            print("❌ Invalid SARIF version")
            return False

        runs = sarif_doc.get("runs", [])
        if len(runs) == 0:
            print("❌ No runs found in SARIF document")
            return False

        total_results = sum(len(run.get("results", [])) for run in runs)
        if total_results == 0:
            print("❌ No results found in SARIF document")
            return False

        print(f"✅ SARIF converter test passed - {total_results} results in {len(runs)} runs")
        return True

    except Exception as e:
        print(f"❌ SARIF converter test failed: {e}")
        return False
    finally:
        # Clean up
        try:
            import shutil
            shutil.rmtree(reports_dir)
        except:
            pass

def test_sarif_merge():
    """Test SARIF merge functionality."""
    print("Testing SARIF merge...")

    sarif_merge = Path("modules/sarif_merge.py")
    if not sarif_merge.exists():
        print("❌ SARIF merge tool not found")
        return False

    # Create sample SARIF files
    test_dir = Path("test_merge")
    test_dir.mkdir(exist_ok=True)

    sarif1 = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [{
            "tool": {"driver": {"name": "tool1"}},
            "results": [
                {"ruleId": "rule1", "message": {"text": "Issue 1"}, "level": "warning"}
            ]
        }]
    }

    sarif2 = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [{
            "tool": {"driver": {"name": "tool2"}},
            "results": [
                {"ruleId": "rule2", "message": {"text": "Issue 2"}, "level": "error"}
            ]
        }]
    }

    with open(test_dir / "sarif1.json", "w") as f:
        json.dump(sarif1, f)

    with open(test_dir / "sarif2.json", "w") as f:
        json.dump(sarif2, f)

    try:
        result = subprocess.run([
            sys.executable, str(sarif_merge),
            str(test_dir / "merged.sarif"),
            str(test_dir / "sarif1.json"),
            str(test_dir / "sarif2.json")
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ SARIF merge failed: {result.stderr}")
            return False

        # Check merged file
        merged_file = test_dir / "merged.sarif"
        if not merged_file.exists():
            print("❌ Merged SARIF file was not created")
            return False

        with open(merged_file) as f:
            merged_doc = json.load(f)

        runs = merged_doc.get("runs", [])
        if len(runs) != 1:
            print(f"❌ Expected 1 merged run, got {len(runs)}")
            return False

        results = runs[0].get("results", [])
        if len(results) != 2:
            print(f"❌ Expected 2 merged results, got {len(results)}")
            return False

        print("✅ SARIF merge test passed")
        return True

    except Exception as e:
        print(f"❌ SARIF merge test failed: {e}")
        return False
    finally:
        # Clean up
        try:
            import shutil
            shutil.rmtree(test_dir)
        except:
            pass

def main():
    """Run all SARIF tests."""
    print("🧪 Running SARIF functionality tests...\n")

    tests = [
        test_sarif_converter,
        test_sarif_merge
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All SARIF tests passed!")
        return 0
    else:
        print("❌ Some SARIF tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())