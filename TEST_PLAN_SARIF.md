# SARIF Merger - Comprehensive Test Plan

> **Feature**: Universal SARIF Merger (Task T1A.1 from MASTER_ROADMAP.md)
> **Goal**: Merge clang-tidy, IWYU, cppcheck, gcc, clang outputs into unified SARIF

---

## Testing Strategy Overview

**Test Pyramid:**
```
       ┌─────────────────┐
       │  E2E Tests (3)  │  Real tools on real C++ code
       └─────────────────┘
            ┌───────────────────────┐
            │ Integration Tests (8) │  Tool output → SARIF
            └───────────────────────┘
                ┌─────────────────────────────┐
                │    Unit Tests (15+)         │  Individual functions
                └─────────────────────────────┘
```

**Test Execution Time Target**: <5 seconds for all tests

---

## Layer 1: Unit Tests (Fast, Isolated)

### 1.1 SARIF Schema Validation

**Test**: `test_sarif_schema_compliance`
- **Input**: Generated SARIF documents
- **Validation**: Against official SARIF 2.1.0 JSON schema
- **How**: Use `jsonschema` library with SARIF spec from OASIS
- **Expected**: All generated SARIF passes schema validation

**Test**: `test_required_fields_present`
- **Check**: `version`, `$schema`, `runs`, `tool.driver.name`
- **Expected**: No missing required fields

---

### 1.2 Deduplication Logic

**Test**: `test_identical_results_deduplicated`
- **Input**: Same diagnostic from 2 different tools
- **Expected**: Only 1 result in merged output
- **Validation**: `compute_result_hash()` works correctly

**Test**: `test_similar_results_not_deduplicated`
- **Input**: Same file/line but different rule IDs
- **Expected**: 2 separate results (not duplicates)

**Test**: `test_deduplication_preserves_first_occurrence`
- **Input**: Duplicate results with different metadata
- **Expected**: First occurrence preserved, later ones dropped

**Test**: `test_empty_results_deduplication`
- **Input**: Empty results list
- **Expected**: No crashes, empty output

---

### 1.3 Severity Mapping

**Test**: `test_severity_mapping_all_levels`
- **Input**: error, warning, note, remark, style, fatal, info
- **Expected**: Correct mapping to SARIF levels (error/warning/note)
- **Function**: `map_severity_to_sarif_level()`

**Test**: `test_unknown_severity_defaults_to_warning`
- **Input**: "critical", "debug", "trace"
- **Expected**: Maps to "warning" (safe default)

---

### 1.4 Rule Consolidation

**Test**: `test_rules_deduplicated_by_id`
- **Input**: Same rule ID from multiple runs
- **Expected**: Only 1 rule definition in merged output

**Test**: `test_rules_preserve_metadata`
- **Input**: Rules with helpUri, descriptions
- **Expected**: All metadata preserved in merge

**Test**: `test_rules_from_all_tools_included`
- **Input**: clang-tidy, cppcheck, IWYU rules
- **Expected**: All unique rules present in merged output

---

### 1.5 Location Handling

**Test**: `test_file_paths_normalized`
- **Input**: Relative paths, absolute paths, Windows-style paths
- **Expected**: Consistent URI format with `%SRCROOT%` base ID

**Test**: `test_line_column_preserved`
- **Input**: Various line/column numbers
- **Expected**: Exact values preserved in merged SARIF

**Test**: `test_multiple_locations_per_result`
- **Input**: cppcheck issue with secondary locations
- **Expected**: `relatedLocations` array populated correctly

---

### 1.6 Fix Suggestions

**Test**: `test_clang_tidy_fixes_converted`
- **Input**: clang-tidy fixes with replacements
- **Expected**: SARIF `fixes` array with `artifactChanges`

**Test**: `test_fixes_attached_to_correct_result`
- **Input**: Multiple diagnostics, some with fixes
- **Expected**: Fixes only on relevant results

---

### 1.7 Statistics & Reporting

**Test**: `test_statistics_calculation`
- **Input**: Merged SARIF with known counts
- **Expected**: Accurate `total_results`, `results_by_level`, `results_by_tool`

**Test**: `test_unique_files_counted_correctly`
- **Input**: Results from 5 files, some duplicates
- **Expected**: Correct unique file count

---

### 1.8 Edge Cases

**Test**: `test_empty_input_files`
- **Input**: Empty JSON files
- **Expected**: Graceful handling, no crashes

**Test**: `test_malformed_json`
- **Input**: Invalid JSON syntax
- **Expected**: Warning logged, file skipped, other files processed

**Test**: `test_missing_required_fields_in_input`
- **Input**: JSON missing "tool", "diagnostics", etc.
- **Expected**: Defensive handling, defaults applied

**Test**: `test_unicode_in_messages`
- **Input**: Diagnostics with emoji, Chinese, special characters
- **Expected**: Correct UTF-8 encoding in output

**Test**: `test_very_long_file_paths`
- **Input**: Paths >260 chars (Windows MAX_PATH)
- **Expected**: No truncation, correct handling

**Test**: `test_zero_line_column`
- **Input**: line=0, column=0 (invalid)
- **Expected**: Default to line=1, column=1

---

## Layer 2: Integration Tests (Tool Output → SARIF)

### 2.1 Real Tool Output Fixtures

**Setup**: Capture real output from actual tools running on sample C++ code

**Test**: `test_real_clang_tidy_conversion`
- **Input**: `fixtures/clang-tidy-real-output.json` (from actual clang-tidy run)
- **Expected**: Valid SARIF with all diagnostics converted

**Test**: `test_real_cppcheck_conversion`
- **Input**: `fixtures/cppcheck-real-output.json`
- **Expected**: Valid SARIF, all severities mapped correctly

**Test**: `test_real_iwyu_conversion`
- **Input**: `fixtures/iwyu-real-output.json`
- **Expected**: Suggestions converted to SARIF notes

**Test**: `test_gcc_sarif_native_output`
- **Input**: GCC 15+ native SARIF output
- **Expected**: Passed through or merged correctly

**Test**: `test_clang_sarif_native_output`
- **Input**: Clang native SARIF output
- **Expected**: Merged with other tools

---

### 2.2 Multi-Tool Merging

**Test**: `test_merge_all_three_tools`
- **Input**: clang-tidy + cppcheck + IWYU outputs
- **Expected**: Single SARIF with 3 runs or 1 merged run
- **Validation**: Counts match sum of inputs (minus duplicates)

**Test**: `test_merge_preserves_all_severities`
- **Input**: Mix of errors, warnings, notes
- **Expected**: All severity levels present in output

**Test**: `test_merge_with_overlapping_files`
- **Input**: 2 tools analyzing same file
- **Expected**: Results from both tools, no false deduplication

---

### 2.3 Command-Line Interface

**Test**: `test_cli_invocation`
- **Input**: `python modules/sarif_converter.py output.sarif tool1.json tool2.json`
- **Expected**: Exit code 0, output file created

**Test**: `test_cli_missing_input_files`
- **Input**: Non-existent input paths
- **Expected**: Warning logged, exit code 0 (graceful degradation)

**Test**: `test_cli_statistics_mode`
- **Input**: `python modules/sarif_merge.py --stats merged.sarif`
- **Expected**: JSON statistics printed to stdout

**Test**: `test_cli_filter_mode`
- **Input**: `python modules/sarif_merge.py --filter error input.sarif output.sarif`
- **Expected**: Only error-level results in output

---

## Layer 3: End-to-End Tests (Real Tools on Real Code)

### 3.1 Complete Workflow

**Test**: `test_e2e_simple_cpp_project`
- **Setup**:
  1. Create minimal C++ project with known issues:
     - `test.cpp` with nullptr vs NULL (clang-tidy)
     - Null pointer dereference (cppcheck)
     - Missing includes (IWYU)
  2. Run `llmtk analyze --sarif`
  3. Validate output

- **Expected**:
  - `exports/reports/analysis.sarif` exists
  - Contains 3+ results (one per tool)
  - Valid against SARIF schema
  - Viewable in VS Code SARIF viewer

**Test**: `test_e2e_no_issues_found`
- **Setup**: Perfect C++ code with no warnings
- **Expected**: Valid SARIF with 0 results, no errors

**Test**: `test_e2e_large_codebase`
- **Setup**: Project with 100+ files, 1000+ diagnostics
- **Expected**:
  - Completes in <60 seconds
  - Deduplication works at scale
  - Output file <10MB

---

## Test Fixtures Design

### Directory Structure

```
tests/
├── fixtures/
│   ├── sample_code/              # Real C++ files with known issues
│   │   ├── test_nullptr.cpp      # modernize-use-nullptr
│   │   ├── test_memory.cpp       # null pointer dereference
│   │   ├── test_includes.cpp     # missing includes
│   │   └── CMakeLists.txt
│   ├── tool_outputs/             # Pre-captured tool outputs
│   │   ├── clang-tidy-basic.json
│   │   ├── clang-tidy-fixes.json
│   │   ├── cppcheck-errors.json
│   │   ├── cppcheck-multifile.json
│   │   ├── iwyu-suggestions.json
│   │   ├── gcc-sarif-native.sarif
│   │   └── clang-sarif-native.sarif
│   └── expected_outputs/         # Expected SARIF results
│       ├── merged-all-tools.sarif
│       ├── deduplicated.sarif
│       └── filtered-errors-only.sarif
├── unit/
│   ├── test_sarif_converter.py   # Unit tests for conversion
│   ├── test_sarif_merge.py       # Unit tests for merging
│   └── test_severity_mapping.py
├── integration/
│   ├── test_tool_integration.py  # Real tool outputs
│   └── test_cli.py               # Command-line interface
└── e2e/
    └── test_full_workflow.py     # End-to-end scenarios
```

---

## Sample Test Code Snippets

### Test Fixture: C++ Code with Known Issues

```cpp
// tests/fixtures/sample_code/test_nullptr.cpp
#include <cstddef>

void modernize_issues() {
    int* ptr = NULL;  // modernize-use-nullptr
    char* str = 0;    // modernize-use-nullptr
}

void null_dereference() {
    int* ptr = nullptr;
    *ptr = 42;  // cppcheck: null pointer dereference
}

// Missing #include <memory> for std::unique_ptr (IWYU)
// std::unique_ptr<int> makeInt() { return std::make_unique<int>(5); }
```

### Unit Test Example

```python
# tests/unit/test_sarif_converter.py
import pytest
from modules.sarif_converter import map_severity_to_sarif_level

class TestSeverityMapping:
    def test_error_levels_map_to_error(self):
        assert map_severity_to_sarif_level("error") == "error"
        assert map_severity_to_sarif_level("fatal error") == "error"
        assert map_severity_to_sarif_level("fatal") == "error"

    def test_warning_levels_map_to_warning(self):
        assert map_severity_to_sarif_level("warning") == "warning"
        assert map_severity_to_sarif_level("warn") == "warning"

    def test_info_levels_map_to_note(self):
        assert map_severity_to_sarif_level("note") == "note"
        assert map_severity_to_sarif_level("info") == "note"
        assert map_severity_to_sarif_level("remark") == "note"

    def test_unknown_severity_defaults_to_warning(self):
        assert map_severity_to_sarif_level("critical") == "warning"
        assert map_severity_to_sarif_level("") == "warning"
```

### Integration Test Example

```python
# tests/integration/test_tool_integration.py
import json
import pytest
from pathlib import Path
from modules.sarif_converter import convert_clang_tidy_to_sarif

def test_real_clang_tidy_conversion():
    """Test conversion of actual clang-tidy output."""
    fixture_path = Path("tests/fixtures/tool_outputs/clang-tidy-basic.json")

    with open(fixture_path) as f:
        clang_tidy_report = json.load(f)

    run = convert_clang_tidy_to_sarif(clang_tidy_report, Path("."))

    # Validate structure
    assert run["tool"]["driver"]["name"] == "clang-tidy"
    assert len(run["results"]) > 0

    # Validate first result
    result = run["results"][0]
    assert "ruleId" in result
    assert "message" in result
    assert "locations" in result

    # Validate location structure
    location = result["locations"][0]
    assert "physicalLocation" in location
    assert "artifactLocation" in location["physicalLocation"]
    assert "region" in location["physicalLocation"]
```

### E2E Test Example

```python
# tests/e2e/test_full_workflow.py
import subprocess
import json
from pathlib import Path

def test_e2e_analyze_sample_project(tmp_path):
    """End-to-end test of llmtk analyze on sample C++ project."""
    # Setup: Copy sample project to temp directory
    sample_project = Path("tests/fixtures/sample_code")
    project_dir = tmp_path / "test_project"
    shutil.copytree(sample_project, project_dir)

    # Run llmtk analyze
    result = subprocess.run(
        ["llmtk", "analyze", "--sarif", str(project_dir)],
        cwd=project_dir,
        capture_output=True,
        text=True
    )

    # Validate command succeeded
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Validate SARIF output exists
    sarif_path = project_dir / "exports/reports/analysis.sarif"
    assert sarif_path.exists(), "SARIF output not created"

    # Validate SARIF structure
    with open(sarif_path) as f:
        sarif_doc = json.load(f)

    assert sarif_doc["version"] == "2.1.0"
    assert len(sarif_doc["runs"]) > 0

    # Validate we found expected issues
    total_results = sum(len(run["results"]) for run in sarif_doc["runs"])
    assert total_results >= 3, "Expected at least 3 diagnostics"

    # Validate schema compliance
    validate_sarif_schema(sarif_doc)
```

---

## Validation Utilities

### SARIF Schema Validator

```python
# tests/utils/sarif_validator.py
import json
import jsonschema
from pathlib import Path

def validate_sarif_schema(sarif_doc: dict) -> bool:
    """Validate SARIF document against official schema."""
    schema_path = Path("tests/schemas/sarif-schema-2.1.0.json")

    if not schema_path.exists():
        # Download schema if not present
        import urllib.request
        schema_url = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(schema_url, schema_path)

    with open(schema_path) as f:
        schema = json.load(f)

    try:
        jsonschema.validate(instance=sarif_doc, schema=schema)
        return True
    except jsonschema.ValidationError as e:
        print(f"Schema validation failed: {e}")
        return False
```

---

## Test Execution

### Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# E2E tests (slow)
pytest tests/e2e/ -v --timeout=60

# With coverage
pytest tests/ --cov=modules --cov-report=html

# Generate JUnit XML for CI
pytest tests/ --junitxml=test-results.xml
```

### CI Integration

```yaml
# .github/workflows/test-sarif.yml
name: SARIF Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install dependencies
        run: |
          pip install pytest jsonschema
          sudo apt-get install -y clang-tidy cppcheck

      - name: Run unit tests
        run: pytest tests/unit/ -v

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Run E2E tests
        run: pytest tests/e2e/ -v --timeout=120

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test-results.xml
```

---

## Manual Testing Checklist

Beyond automated tests, manually verify:

- [ ] View merged SARIF in VS Code SARIF Viewer extension
- [ ] Upload to GitHub Code Scanning (validates schema + displays correctly)
- [ ] Open in other SARIF viewers (Microsoft SARIF Viewer, SARIF Multitool)
- [ ] Verify hyperlinks (helpUri) work correctly
- [ ] Check performance on large real-world project (>100k LOC)
- [ ] Test with non-ASCII file paths (Japanese, emoji, etc.)

---

## Test Maintenance

**When to update tests:**
- Adding support for new analysis tools (gcc, clang native SARIF)
- Changing SARIF schema version (2.1.0 → 2.2.0)
- Modifying deduplication algorithm
- Adding new filters or statistics

**Test data updates:**
- Re-capture tool outputs when tool versions change
- Update expected outputs when converter logic improves
- Add new fixtures for reported bugs

---

## Success Criteria

**Before merging SARIF merger implementation:**

- ✅ All unit tests pass (15+ tests)
- ✅ All integration tests pass (8+ tests)
- ✅ At least 1 E2E test passes
- ✅ Test coverage >80% for sarif_converter.py and sarif_merge.py
- ✅ SARIF schema validation passes for all generated outputs
- ✅ Manual verification in at least 1 SARIF viewer

**Performance targets:**
- Unit tests complete in <1 second
- Integration tests complete in <5 seconds
- E2E tests complete in <30 seconds

---

## Next Steps

1. **Create test infrastructure** (Week 1):
   - Set up pytest configuration
   - Create fixtures directory structure
   - Download SARIF schema for validation
   - Capture real tool outputs

2. **Implement unit tests** (Week 1):
   - Start with severity mapping tests (easiest)
   - Add deduplication tests
   - Add edge case tests

3. **Implement integration tests** (Week 2):
   - Test each tool converter separately
   - Test merge functionality
   - Test CLI interface

4. **Implement E2E tests** (Week 2):
   - Create sample C++ project
   - Test full workflow
   - Validate against schema

5. **Continuous improvement**:
   - Add tests for every bug found
   - Expand coverage for edge cases
   - Performance benchmarking

---

**Last Updated**: 2025-11-20
**Status**: Ready for implementation
