# SARIF Analysis and Fix-it Loop Guide

This guide covers the new Universal SARIF analysis and fix-it loop functionality in `llmtk`.

## Overview

The SARIF (Static Analysis Results Interchange Format) support provides:

- **Universal format**: Convert clang-tidy, cppcheck, and IWYU results to standardized SARIF
- **Merge and deduplicate**: Combine multiple tool results into single reports
- **CI gating**: Enforce severity budgets to maintain code quality
- **Fix application**: Apply suggested fixes with integrated tools

## Quick Start

```bash
# Run analysis with SARIF output
llmtk analyze --sarif src/

# Apply clang-tidy fixes
llmtk tidy --apply src/

# Check code formatting
llmtk format --check src/

# Gate CI with severity budgets
llmtk gate exports/reports/analysis.sarif --max-warnings=5
```

## Commands

### `llmtk analyze --sarif`

Runs clang-tidy, cppcheck, and IWYU, then converts results to SARIF format.

```bash
# Basic SARIF analysis
llmtk analyze --sarif

# Analyze specific paths
llmtk analyze --sarif src/ include/

# Output files:
# - exports/reports/clang-tidy.json
# - exports/reports/cppcheck.json
# - exports/reports/iwyu.json
# - exports/reports/analysis.sarif (when --sarif used)
```

### `llmtk tidy --apply`

Run clang-tidy with automatic fix application.

```bash
# Check issues without fixing
llmtk tidy src/

# Apply all fixes
llmtk tidy --apply src/

# Apply specific checks only
llmtk tidy --apply --checks="modernize-*,readability-*" src/
```

### `llmtk format --check|--apply`

Run clang-format with different modes.

```bash
# Check formatting (dry run)
llmtk format --check src/

# Apply formatting
llmtk format --apply src/

# Use specific style
llmtk format --apply --style=Google src/
```

### `llmtk gate`

Enforce SARIF severity budgets for CI gating.

```bash
# Basic gating with defaults (0 errors, 10 warnings, 50 notes)
llmtk gate exports/reports/analysis.sarif

# Custom limits
llmtk gate --max-errors=0 --max-warnings=5 analysis.sarif

# Use configuration file
llmtk gate --config=.llmtk-gate.yaml analysis.sarif
```

## SARIF Format

The generated SARIF files follow the [SARIF 2.1.0 specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html).

### Example SARIF Structure

```json
{
  "version": "2.1.0",
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "clang-tidy",
          "version": "14.0.0",
          "rules": [
            {
              "id": "modernize-use-nullptr",
              "shortDescription": {"text": "clang-tidy check: modernize-use-nullptr"}
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "modernize-use-nullptr",
          "message": {"text": "Use nullptr instead of NULL"},
          "level": "warning",
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {"uri": "src/main.cpp"},
                "region": {"startLine": 42, "startColumn": 15}
              }
            }
          ]
        }
      ]
    }
  ]
}
```

## Gate Configuration

Create `.llmtk-gate.yaml` to customize severity budgets:

```yaml
# Maximum allowed issues by severity
max_errors: 0
max_warnings: 15
max_notes: 100

# Optional: Rule-specific overrides
rule_overrides:
  clang-tidy:
    max_warnings: 10
  cppcheck:
    max_errors: 0

# Optional: File pattern exclusions
exclude_patterns:
  - "*/third_party/*"
  - "*/generated/*"
  - "test_*.cpp"

# Optional: Custom severity mapping
severity_mapping:
  style: note
  performance: warning
  security: error
```

## CI Integration

### GitHub Actions Example

```yaml
name: Static Analysis
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install llmtk
        run: curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash

      - name: Export build context
        run: llmtk context export

      - name: Run SARIF analysis
        run: llmtk analyze --sarif src/

      - name: Apply clang-tidy fixes
        run: llmtk tidy --apply src/

      - name: Check formatting
        run: llmtk format --check src/

      - name: Gate on severity budgets
        run: llmtk gate exports/reports/analysis.sarif --max-warnings=10

      - name: Upload SARIF results
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: exports/reports/analysis.sarif
```

### GitLab CI Example

```yaml
static_analysis:
  stage: test
  script:
    - curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash
    - llmtk context export
    - llmtk analyze --sarif src/
    - llmtk gate exports/reports/analysis.sarif
  artifacts:
    reports:
      codequality: exports/reports/analysis.sarif
    paths:
      - exports/
    expire_in: 1 week
```

## SARIF Tools and Utilities

### Merge Multiple SARIF Files

```bash
# Merge multiple SARIF files with deduplication
python3 modules/sarif_merge.py merged.sarif file1.sarif file2.sarif

# Get statistics about a SARIF file
python3 modules/sarif_merge.py --stats analysis.sarif

# Filter by severity level
python3 modules/sarif_merge.py --filter warning input.sarif filtered.sarif
```

### Convert Individual Reports

```bash
# Convert specific tool reports to SARIF
python3 modules/sarif_converter.py output.sarif clang-tidy.json cppcheck.json iwyu.json
```

## Best Practices

### 1. Progressive Improvement

Start with relaxed budgets and gradually tighten:

```yaml
# Week 1: Baseline
max_errors: 5
max_warnings: 50

# Week 4: Tighter
max_errors: 2
max_warnings: 30

# Week 8: Strict
max_errors: 0
max_warnings: 10
```

### 2. Tool-Specific Configuration

Use different budgets for different tools:

```yaml
rule_overrides:
  clang-tidy:
    max_warnings: 5      # Strict for maintainability
  cppcheck:
    max_warnings: 15     # More lenient for style issues
  include-what-you-use:
    max_notes: 20        # Moderate for include optimization
```

### 3. Exclude Generated Code

```yaml
exclude_patterns:
  - "*/build/*"
  - "*/third_party/*"
  - "*_generated.cpp"
  - "*/protobuf/*"
```

### 4. Fix Application Workflow

```bash
# 1. Check current state
llmtk analyze --sarif src/
llmtk gate exports/reports/analysis.sarif

# 2. Apply automatic fixes
llmtk tidy --apply src/
llmtk format --apply src/

# 3. Re-check after fixes
llmtk analyze --sarif src/
llmtk gate exports/reports/analysis.sarif

# 4. Review changes before commit
git diff
```

## Tool Coverage

| Tool | SARIF Support | Fix Application | Coverage |
|------|---------------|-----------------|----------|
| clang-tidy | ✅ Full | ✅ `--apply` | Modernization, readability, performance |
| cppcheck | ✅ Full | ❌ Manual | Memory safety, undefined behavior |
| IWYU | ✅ Full | ❌ Manual | Include optimization |
| clang-format | ➖ N/A | ✅ `--apply` | Code formatting |

## Troubleshooting

### Missing compile_commands.json

```bash
# Generate compilation database
llmtk context export

# Alternative: use bear
bear -- make
```

### Empty SARIF Results

```bash
# Check tool availability
llmtk doctor

# Verify paths contain C++ files
llmtk analyze src/ include/

# Check for compilation errors
cmake --build build 2>&1 | grep error
```

### Gate Failures

```bash
# Get detailed breakdown
llmtk gate --max-warnings=0 analysis.sarif

# Review specific issues
python3 modules/sarif_merge.py --stats analysis.sarif

# Filter to error-level only
python3 modules/sarif_merge.py --filter error analysis.sarif errors-only.sarif
```

## Integration with IDEs

### VS Code

The SARIF files can be consumed by VS Code extensions:

1. Install "SARIF Viewer" extension
2. Open SARIF file: `exports/reports/analysis.sarif`
3. View results in Problems panel

### CLion/IntelliJ

Use the built-in SARIF support:

1. Go to Code → Inspect Code → Import External Results
2. Select SARIF format and choose `analysis.sarif`
3. Review results in Inspection Results panel

## Performance Tips

### Large Codebases

```bash
# Analyze incrementally
llmtk analyze --sarif src/core/
llmtk analyze --sarif src/ui/

# Merge results
python3 modules/sarif_merge.py final.sarif exports/reports/analysis.sarif

# Use parallel processing
LLMTK_PARALLEL=4 llmtk analyze --sarif src/
```

### CI Optimization

```yaml
# Cache build artifacts
cache:
  paths:
    - build/
    - exports/compile_commands.json

# Skip analysis on docs-only changes
rules:
  changes:
    - "**/*.cpp"
    - "**/*.h"
    - CMakeLists.txt
```

This completes the Universal SARIF analysis and fix-it loop implementation for llmtk!