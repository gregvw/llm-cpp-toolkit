# Test Suite for llm-cpp-toolkit

This directory contains the test suite for the LLM C++ Toolkit.

## Directory Structure

```
tests/
├── fixtures/                      # Test fixtures and sample data
│   ├── sample_code/              # Sample C++ code with known issues
│   │   ├── test_nullptr.cpp      # modernize-use-nullptr issues
│   │   ├── test_memory.cpp       # Memory and pointer issues
│   │   ├── test_includes.cpp     # Include optimization issues
│   │   ├── CMakeLists.txt        # Build configuration
│   │   └── build/                # Build artifacts (gitignored)
│   ├── tool_outputs/             # Pre-captured tool outputs
│   │   ├── clang-tidy-modernize.json
│   │   ├── cppcheck-memory-errors.json
│   │   └── iwyu-include-suggestions.json
│   └── expected_outputs/         # Expected SARIF outputs
├── unit/                         # Unit tests (fast, isolated)
├── integration/                  # Integration tests (tools + conversion)
├── e2e/                          # End-to-end tests (full workflow)
├── utils/                        # Test utilities
│   ├── sarif_validator.py        # SARIF validation helpers
│   └── __init__.py
└── schemas/                      # JSON schemas for validation
    └── README.md                 # Schema documentation
```

## Running Tests

### All Tests

```bash
pytest tests/
```

### By Category

```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# End-to-end tests
pytest tests/e2e/ -v
```

### By Marker

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### With Coverage

```bash
pytest tests/ --cov=llmtk --cov=modules --cov-report=html
```

## Test Markers

Tests are marked with the following markers (defined in `pytest.ini`):

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (moderate speed)
- `@pytest.mark.e2e` - End-to-end tests (slow)
- `@pytest.mark.slow` - Tests that take >1 second
- `@pytest.mark.requires_tools` - Tests that need external tools

## Writing Tests

### Unit Tests

Unit tests should:
- Be fast (<100ms)
- Test individual functions in isolation
- Use mocks/fixtures for dependencies
- Not require external tools

Example:
```python
import pytest
from modules.sarif_converter import map_severity_to_sarif_level

@pytest.mark.unit
def test_severity_mapping():
    assert map_severity_to_sarif_level("error") == "error"
    assert map_severity_to_sarif_level("warning") == "warning"
```

### Integration Tests

Integration tests should:
- Test components working together
- Use real tool outputs (from fixtures)
- Validate against SARIF schema
- Complete in <5 seconds

Example:
```python
import pytest
from pathlib import Path
from modules.sarif_converter import convert_clang_tidy_to_sarif
from tests.utils import assert_sarif_valid

@pytest.mark.integration
def test_clang_tidy_conversion():
    fixture = Path("tests/fixtures/tool_outputs/clang-tidy-modernize.json")
    with open(fixture) as f:
        report = json.load(f)

    run = convert_clang_tidy_to_sarif(report, Path("."))
    assert_sarif_valid({"version": "2.1.0", "runs": [run]})
```

### End-to-End Tests

E2E tests should:
- Test complete workflows
- Run real commands (llmtk analyze)
- Verify output files exist and are valid
- May take 10-30 seconds

Example:
```python
import pytest
import subprocess
from pathlib import Path
from tests.utils import assert_sarif_valid

@pytest.mark.e2e
@pytest.mark.slow
def test_analyze_with_sarif(tmp_path):
    # Copy sample project
    # Run llmtk analyze --sarif
    # Validate output
    pass
```

## Test Utilities

### SARIF Validation

```python
from tests.utils import (
    assert_sarif_valid,           # Assert document is valid SARIF
    assert_sarif_has_results,     # Assert minimum result count
    assert_sarif_has_run,          # Assert tool is present
    get_sarif_statistics,         # Get counts and breakdowns
    validate_sarif_structure,     # Get list of validation errors
)
```

### Loading Fixtures

```python
from tests.utils import load_sarif_fixture

sarif_doc = load_sarif_fixture("expected_analysis.sarif")
```

## Fixtures

### Sample C++ Code

Located in `tests/fixtures/sample_code/`:
- Configured with CMake
- Generates `compile_commands.json`
- Contains known issues for testing

To rebuild:
```bash
cd tests/fixtures/sample_code
cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

### Tool Outputs

Located in `tests/fixtures/tool_outputs/`:
- Real tool outputs captured from sample code
- JSON format matching our converter expectations
- Updated when tool formats change

### Expected Outputs

Located in `tests/fixtures/expected_outputs/`:
- Reference SARIF outputs for comparison
- Used in regression testing
- Manually verified for correctness

## Continuous Integration

Tests run automatically on:
- Every push
- Pull requests
- Daily schedule (full suite including slow tests)

See `.github/workflows/test.yml` for CI configuration.

## Test Coverage

Target: >80% coverage for:
- `llmtk/` - Main CLI code
- `modules/` - Shell/Python modules

View coverage report:
```bash
pytest tests/ --cov=llmtk --cov=modules --cov-report=html
open htmlcov/index.html
```

## Troubleshooting

### Tests Failing Locally

1. **Install test dependencies:**
   ```bash
   pip install pytest pytest-cov
   ```

2. **Ensure external tools are available:**
   ```bash
   llmtk doctor
   ```

3. **Rebuild fixtures if needed:**
   ```bash
   cd tests/fixtures/sample_code
   rm -rf build
   cmake -B build
   ```

### Slow Tests

Mark slow tests with `@pytest.mark.slow`:
```python
@pytest.mark.slow
def test_large_codebase():
    # Test that takes >1 second
    pass
```

Skip slow tests:
```bash
pytest -m "not slow"
```

## Contributing

When adding new features:
1. Write tests FIRST (TDD)
2. Add unit tests for new functions
3. Add integration tests for new commands
4. Update fixtures if tool formats change
5. Ensure >80% coverage

---

Last Updated: 2025-11-20
