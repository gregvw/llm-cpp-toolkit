# Toolkit Reference

Generated from manifests on 2025-09-19T04:30:34.265831+00:00.

## Tools
- bat
  - provides: pager
  - check: `batcat --version`
- bear
  - provides: compile-db
  - check: `bear --version`
- bottom
  - provides: monitor
  - check: `btm --version`
- ccache
  - provides: cache
  - check: `ccache --version`
- cheat
  - provides: cheatsheets
  - check: `cheat --version`
- clang-format
  - provides: format
  - check: `clang-format --version`
- clang-tidy
  - provides: lint, analysis
  - check: `clang-tidy --version`
- clangd
  - provides: lsp, xref, refactor
  - check: `clangd --version`
- cmake
  - provides: build, configure
  - check: `cmake --version`
- cppcheck
  - provides: static-analysis
  - check: `cppcheck --version`
- creduce
  - provides: reducer
  - check: `creduce --version`
- cvise
  - provides: reducer
  - check: `cvise --version`
- delta
  - provides: git-pager
  - check: `delta --version`
- difftastic
  - provides: diff
  - check: `difft --version`
- entr
  - provides: watch
  - check: `entr -v`
- eza
  - provides: ls
  - check: `eza --version`
- fd
  - provides: file-find
  - check: `fdfind --version`
- fzf
  - provides: fuzzy-find
  - check: `fzf --version`
- git
  - provides: version-control
  - check: `git --version`
- httpie
  - provides: http-client
  - check: `http --version`
- hyperfine
  - provides: benchmark
  - check: `hyperfine --version`
- include-what-you-use
  - provides: include-analysis
  - check: `include-what-you-use --version`
- iwyu-tool
  - provides: include-analysis
  - check: `iwyu_tool --help`
- jq
  - provides: json
  - check: `jq --version`
- mold
  - provides: linker
  - check: `mold --version`
- ninja
  - provides: build-backend
  - check: `ninja --version`
- pre-commit
  - provides: hooks
  - check: `pre-commit --version`
- procs
  - provides: ps
  - check: `procs --version`
- rg
  - provides: search
  - check: `rg --version`
- tldr
  - provides: docs
  - check: `tldr --version`
- tokei
  - provides: code-stats
  - check: `tokei --version`
- tree
  - provides: tree
  - check: `tree --version`
- universal-ctags
  - provides: indexing
  - check: `ctags --version`
- yq
  - provides: yaml
  - check: `yq --version`
- zoxide
  - provides: jump
  - check: `zoxide -V`

## Commands
- analyze
  - description: Run clang-tidy + IWYU + cppcheck with JSON reports.
  - args: paths (variadic), sarif
  - runs: modules/analyze.sh
  - output: exports/reports/clang-tidy.json
    schema:
    ```json
    {
      "available": "bool",
      "version": "string|null",
      "inputs": [
        "string"
      ],
      "diagnostics": [
        {
          "file": "string",
          "line": "int",
          "col": "int",
          "severity": "string",
          "msg": "string",
          "check": "string|null"
        }
      ],
      "fixes": [
        {
          "file": "string",
          "message": "string",
          "file_offset": "int",
          "replacements": [
            {
              "file": "string",
              "offset": "int",
              "length": "int",
              "replacement": "string"
            }
          ]
        }
      ]
    }
    ```
  - output: exports/reports/iwyu.json
    schema:
    ```json
    {
      "available": "bool",
      "version": "string|null",
      "suggestions": [
        {
          "file": "string",
          "add": [
            "string"
          ],
          "remove": [
            "string"
          ]
        }
      ]
    }
    ```
  - output: exports/reports/cppcheck.json
    schema:
    ```json
    {
      "available": "bool",
      "version": "string|null",
      "diagnostics": [
        {
          "id": "string",
          "severity": "string",
          "msg": "string",
          "verbose": "string",
          "locations": [
            {
              "file": "string",
              "line": "int",
              "column": "int"
            }
          ]
        }
      ]
    }
    ```
  - output: exports/reports/analysis.sarif
    schema:
    ```json
    {
      "version": "string",
      "$schema": "string",
      "runs": [
        {
          "tool": {
            "driver": {
              "name": "string",
              "version": "string",
              "rules": [
                "object"
              ]
            }
          },
          "results": [
            {
              "ruleId": "string",
              "message": {
                "text": "string"
              },
              "level": "string",
              "locations": [
                "object"
              ]
            }
          ]
        }
      ]
    }
    ```
- capabilities
  - description: Emit machine-readable toolkit capabilities summary.
  - output: exports/capabilities.json
    schema:
    ```json
    {
      "_meta": {
        "generated_at": "string",
        "toolkit_version": "string",
        "tools_manifest": "string",
        "commands_manifest": "string"
      },
      "tools": "object",
      "commands": "object"
    }
    ```
- context-export
  - description: Collect artifacts LLMs rely on.
  - runs: modules/compile_db.sh, modules/cmake_introspect.sh
  - output: exports/compile_commands.json
  - output: exports/cmake-file-api/*.json
  - output: exports/context.json
    schema:
    ```json
    {
      "compile_commands": "string|null",
      "cmake_file_api": {
        "dir": "string",
        "files": [
          "string"
        ]
      },
      "generated_at": "string"
    }
    ```
  - json_summary: exports/context.json
- doctor
  - description: Inspect environment and report tool availability.
  - output: exports/doctor.json
    schema:
    ```json
    {
      "_meta": {
        "generated_at": "string"
      },
      "tool": {
        "found": "bool",
        "path": "string|null",
        "version_line": "string|null"
      }
    }
    ```
- format
  - description: Run clang-format on code with check or apply options.
  - args: paths (variadic), check, apply, style
- gate
  - description: Enforce SARIF severity budgets for CI gating.
  - args: sarif_file (required), max-errors, max-warnings, max-notes, config
  - output: (unknown)
- reduce
  - description: Minimize a failing repro with cvise.
  - args: input (required), test_cmd (required)
  - runs: modules/reduce.sh
  - output: exports/repros/minimized.cpp
  - output: exports/repros/report.json
    schema:
    ```json
    {
      "cvise_available": "bool",
      "exit_code": "int|null",
      "input": "string"
    }
    ```
- stderr-thin
  - description: Collapse compiler stderr into deterministic, budget-aware highlights.
  - args: log, compile, compile-index, level, context-budget
  - output: exports/diagnostics/stderr-thin.json
    schema:
    ```json
    {
      "_meta": {
        "generated_at": "string",
        "level": "string",
        "context_budget": "int",
        "structured_source": "string"
      },
      "counts": {
        "error": "int",
        "warning": "int",
        "note": "int",
        "remark": "int",
        "other": "int"
      },
      "view": {
        "path": "string",
        "level": "string",
        "context_budget": "int",
        "context_used": "int",
        "context_full": "int",
        "context_truncated": "int"
      },
      "highlights": [
        "string"
      ]
    }
    ```
  - output: exports/diagnostics/stderr-thin.txt
  - output: exports/diagnostics/stderr-raw.txt
- test
  - description: Run CTest suites and emit structured results for LLM consumption.
  - args: build-dir, regex, exclude, label, parallel, timeout, rerun-failed, preview, json, sarif
  - output: exports/tests/ctest_results.json
    schema:
    ```json
    {
      "_meta": {
        "generated_at": "string",
        "ctest_command": "string",
        "build_dir": "string",
        "ctest_version": "string|null",
        "return_code": "int",
        "duration_seconds": "number",
        "stdout": "string",
        "stderr": "string",
        "xml": "string|null"
      },
      "stats": {
        "total": "int",
        "passed": "int",
        "failed": "int",
        "timeout": "int",
        "notrun": "int",
        "skipped": "int",
        "unknown": "int",
        "duration_seconds": "number"
      },
      "failures": [
        {
          "name": "string",
          "status": "string",
          "fail_reason": "string|null"
        }
      ],
      "tests": [
        {
          "name": "string",
          "status": "string",
          "duration": "number|null",
          "labels": [
            "string"
          ],
          "fail_reason": "string|null"
        }
      ]
    }
    ```
  - output: exports/tests/ctest_results.sarif
  - output: exports/tests/Test.xml
  - output: exports/tests/ctest_stdout.txt
  - output: exports/tests/ctest_stderr.txt
- tidy
  - description: Run clang-tidy with optional fix application.
  - args: paths (variadic), apply, checks
