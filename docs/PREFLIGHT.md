# Preflight: Fast Syntax and Delimiter Validation

The `llmtk preflight` command provides fast syntax and delimiter validation before expensive build operations. It's designed to catch common LLM-induced errors quickly, preventing build failures and saving development time.

## Table of Contents

- [Overview](#overview)
- [Supported File Types](#supported-file-types)
- [Usage](#usage)
- [Command Line Options](#command-line-options)
- [Output Formats](#output-formats)
- [Integration Patterns](#integration-patterns)
- [Rule Reference](#rule-reference)
- [Examples](#examples)
- [Advanced Features](#advanced-features)

## Overview

Preflight performs two main types of validation:

1. **Delimiter and Quote Checking**: Validates balanced parentheses, brackets, braces, and quotes
2. **External Syntax Probes**: Leverages external tools for comprehensive syntax validation

### Key Benefits

- **Fast**: Syntax checks complete in milliseconds
- **Comprehensive**: Covers multiple file types in a single command
- **LLM-Optimized**: Designed to catch common AI coding assistant errors
- **CI-Ready**: Provides structured output formats (JSON, SARIF)
- **Fail-Fast**: Catches errors before expensive compilation

## Supported File Types

### C/C++ Files (`.c`, `.cpp`, `.h`, `.hpp`, etc.)
- **Primary**: clang syntax checking with `compile_commands.json` integration
- **Fallback**: Tree-sitter parsing for delimiter validation
- **Features**: Include path resolution, define handling, precise error locations

### JSON Files (`.json`)
- **Primary**: Python's `json` module for precise error reporting
- **Secondary**: Optional `jq` validation for additional checks
- **Features**: Exact line/column error positions

### YAML Files (`.yaml`, `.yml`)
- **Primary**: PyYAML parser for syntax validation
- **Secondary**: Optional `yamllint` for style checks
- **Features**: Problem mark extraction, style rule enforcement

### TOML Files (`.toml`)
- **Primary**: Python's `tomllib`/`tomli` for parsing
- **Secondary**: Optional `taplo` validation
- **Features**: Line/column error extraction

### Shell Scripts (`.sh`, `.bash`, `.zsh`)
- **Primary**: bash/zsh syntax checking with `-n` flag
- **Secondary**: Optional `shellcheck` static analysis
- **Features**: Shell type detection, comprehensive rule checking

### CMake Files (`.cmake`, `CMakeLists.txt`)
- **Primary**: `cmake -P` syntax validation
- **Secondary**: Optional `cmake-format` style checking
- **Features**: CMake-specific syntax validation

## Usage

### Basic Syntax

```bash
llmtk preflight [OPTIONS] [FILE_SELECTION]
```

### File Selection Methods

```bash
# Check files changed since last commit
llmtk preflight --diff HEAD~1

# Check files changed between branches
llmtk preflight --diff main...feature-branch

# Check files changed since a reference
llmtk preflight --since origin/main

# Check specific paths
llmtk preflight --paths src/ include/ CMakeLists.txt

# Check with extension filter
llmtk preflight --diff HEAD --extensions .cpp .h .json
```

## Command Line Options

### File Discovery
- `--diff BASE_REF`: Check files changed from BASE_REF
- `--since REF`: Check files changed since REF
- `--paths PATH [PATH...]`: Check explicit paths

### Output Control
- `--json FILE`: Output findings as JSON to FILE
- `--sarif FILE`: Output findings as SARIF to FILE
- `--verbose, -v`: Enable verbose output

### Behavior
- `--strict`: Treat warnings as errors
- `--max-lines N`: Skip files with more than N lines
- `--max-files N`: Check at most N files

### Feature Toggles
- `--no-tree-sitter`: Disable tree-sitter parsing (use fallback)
- `--no-syntax`: Disable external syntax checking
- `--extensions EXT [EXT...]`: Only check files with these extensions

## Output Formats

### Human-Readable (Default)

Clean table format with file paths, locations, and messages:

```
Preflight Issues Found:

File                     Line:Col   Severity Rule              Message
----------------------------------------------------------------------------
src/parser.cpp           42:15      ✗ ERR    unclosed_delimiter Unclosed '{' delimiter
config.json              8:3        ✗ ERR    syntax             JSON parse error: Expecting ',' delimiter

============================================================
Total: 2 issues (2 errors, 0 warnings)
```

### JSON Format

Structured output with comprehensive statistics:

```json
{
  "tool": "llmtk-preflight",
  "version": "1.0.0",
  "generated_at": "2025-09-19T22:05:50.141880",
  "findings": [
    {
      "file": "src/parser.cpp",
      "line": 42,
      "col": 15,
      "rule": "unclosed_delimiter",
      "symbol": "{",
      "message": "Unclosed '{' delimiter",
      "severity": "error",
      "source": "preflight"
    }
  ],
  "summary": {
    "total": 1,
    "errors": 1,
    "warnings": 0,
    "info": 0,
    "by_rule": {
      "unclosed_delimiter": 1
    },
    "by_source": {
      "preflight": 1
    },
    "files_checked": 1
  }
}
```

### SARIF 2.1.0 Format

CI-ready format with rich rule metadata:

```json
{
  "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "llmtk-preflight",
          "rules": [
            {
              "id": "unclosed_delimiter",
              "name": "Unclosed Delimiter",
              "shortDescription": {"text": "Missing closing delimiter"},
              "fullDescription": {"text": "Detects unmatched opening delimiters"},
              "properties": {
                "category": "structure",
                "tags": ["structure"]
              }
            }
          ]
        }
      },
      "results": [...]
    }
  ]
}
```

## Integration Patterns

### Pre-Build Validation

```bash
#!/bin/bash
# build.sh

# Fast syntax check before expensive operations
llmtk preflight --diff HEAD || {
  echo "❌ Syntax errors found. Fix before building."
  exit 1
}

# Proceed with build
cmake --build build
```

### CI/CD Integration

```yaml
# .github/workflows/ci.yml
- name: Fast Syntax Check
  run: |
    llmtk preflight --diff origin/main --strict --sarif reports/preflight.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: reports/preflight.sarif
```

### LLM Agent Integration

```python
# Agent workflow
def validate_changes(files):
    # Fast validation before expensive analysis
    result = subprocess.run([
        "llmtk", "preflight",
        "--paths", *files,
        "--json", "reports/preflight.json"
    ])

    if result.returncode != 0:
        # Parse findings and provide feedback
        with open("reports/preflight.json") as f:
            findings = json.load(f)
        return findings["findings"]

    return []
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: llmtk-preflight
        name: llmtk preflight
        entry: llmtk preflight --paths
        language: system
        files: \\.(cpp|h|json|yaml|sh)$
```

## Rule Reference

### Delimiter Rules

| Rule | Description | Severity | File Types |
|------|-------------|----------|------------|
| `unclosed_delimiter` | Missing closing delimiter | error | All |
| `unbalanced_delimiter` | Mismatched delimiter pairs | error | All |
| `unclosed_quote` | Missing closing quote | error | All |
| `unclosed_code_fence` | Unclosed markdown code fence | error | .md |

### Syntax Rules

| Rule | Description | Tool | File Types |
|------|-------------|------|------------|
| `json_syntax` | JSON parse error | Python json | .json |
| `yaml_syntax` | YAML parse error | PyYAML | .yaml, .yml |
| `toml_syntax` | TOML parse error | tomllib/tomli | .toml |
| `shell_syntax` | Shell syntax error | bash -n | .sh, .bash |
| `cmake_syntax` | CMake syntax error | cmake -P | .cmake, CMakeLists.txt |
| `clang_syntax` | C/C++ syntax error | clang | .c, .cpp, .h, .hpp |

### Style Rules (Optional)

| Rule | Description | Tool | File Types |
|------|-------------|------|------------|
| `yaml_*` | YAML style issues | yamllint | .yaml, .yml |
| `shellcheck_*` | Shell quality issues | shellcheck | .sh, .bash |
| `cmake_format` | CMake formatting | cmake-format | .cmake |

## Examples

### Basic Usage

```bash
# Check changed files
llmtk preflight --diff HEAD~1

# Check specific files with JSON output
llmtk preflight --paths src/main.cpp config.json --json results.json

# Strict mode (warnings become errors)
llmtk preflight --paths . --strict
```

### Advanced Usage

```bash
# Check large codebase with limits
llmtk preflight --diff origin/main --max-files 100 --max-lines 10000

# Filter by file types
llmtk preflight --since HEAD~5 --extensions .cpp .h --verbose

# Generate both JSON and SARIF
llmtk preflight --paths src/ \\
  --json exports/preflight.json \\
  --sarif exports/preflight.sarif
```

### Error Handling

```bash
# Check exit codes
llmtk preflight --diff HEAD
case $? in
  0) echo "✓ No issues found" ;;
  2) echo "⚠ Warnings found" ;;
  3) echo "❌ Errors found"; exit 1 ;;
  10) echo "💥 Internal error"; exit 1 ;;
esac
```

## Advanced Features

### Tree-sitter Integration

When available, preflight uses Tree-sitter for language-aware parsing:

- **Accurate**: Ignores delimiters in comments and strings
- **Fast**: Optimized parsing for structural validation
- **Extensible**: Supports multiple language grammars

### Compile Database Integration

For C/C++ files, preflight integrates with `compile_commands.json`:

- **Include Paths**: Uses project-specific include directories
- **Defines**: Applies preprocessor definitions
- **Standards**: Respects C++ standard settings
- **Flags**: Incorporates compilation flags

### Performance Optimization

- **Parallel Processing**: Multiple file checking
- **Caching**: Grammar and parser instance reuse
- **Size Limits**: Configurable file size thresholds
- **Early Exit**: Stops on first error in strict mode

### Custom Configuration

Future versions will support:

- Custom rule configuration
- Project-specific settings
- Integration with existing linters
- Plugin system for additional checkers

## Troubleshooting

### Common Issues

**"No files to check"**
```bash
# Ensure you have staged/committed changes
git add .
llmtk preflight --diff HEAD

# Or use explicit paths
llmtk preflight --paths src/
```

**"Tool not found" warnings**
```bash
# Install missing tools
llmtk install clang jq yamllint

# Or disable specific probes
llmtk preflight --no-syntax --paths .
```

**Performance issues with large files**
```bash
# Set size limits
llmtk preflight --max-lines 5000 --max-files 50 --diff HEAD
```

### Exit Codes

- `0`: No issues found
- `2`: Warnings only (non-strict mode)
- `3`: Errors found
- `10`: Internal error (configuration, tool failure, etc.)

## See Also

- [QUICKSTART.md](QUICKSTART.md) - Getting started guide
- [AGENTS.md](../AGENTS.md) - LLM agent integration
- [SARIF_GUIDE.md](SARIF_GUIDE.md) - SARIF format details
- [REFERENCE.md](REFERENCE.md) - Complete command reference