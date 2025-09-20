## Recommended Preflight Implementation Plan

Here is a step-by-step guide to building llmtk preflight, blending the best ideas from the [document](QUOTE_AND_BRACE_HELPER.md).

### 1. Build the Core Orchestrator

Start with the Python skeleton proposed. The main entry point will be responsible for:

File Discovery: Implement the logic for --diff, --since, and --paths to determine which files to check. The fileset.py idea is perfect for this.

Dispatcher: Based on the file extension, the orchestrator will decide which checker to run (e.g., .cpp files go to the Clang probe, .json to the jq probe, and .md to the custom delimiter checker).

### 2. Integrate External Syntax Probes

This is the fastest way to get high-value, accurate checks working.

- C/C++: Shell out to clang -fsyntax-only. This is non-negotiable for accuracy. Use the project's `compile_commands.json` to ensure the correct flags, includes, and definitions are used for each file.

- Standard Formats: Add subprocess calls to mature, existing tools. They are fast and reliable.

- JSON: jq . <file>

- YAML: yamllint --format=parsable <file>

- TOML: taplo check <file>

- Shell: bash -n <file>

### 3. Implement the Custom Delimiter Checker

This is the core innovation of llmtk preflight. It will handle languages where a full syntax check is too slow or unavailable.

Recommendation: Use Tree-sitter.

While PEGTL is powerful, Tree-sitter is a better fit for this project for a few key reasons:

- Ecosystem: It integrates seamlessly with Python, fitting perfectly into the existing toolkit without requiring a separate C++ build step.

- Mature Grammars: There are readily available, high-quality grammars for dozens of languages, including all the ones listed (cpp, cmake, markdown, etc.).

- Performance: It's extremely fast and designed for this exact use case (lexing files for structural analysis).

### 4. Unify the Reporting

Create the reporters.py module to handle output. All checkers (external probes and the internal Tree-sitter checker) should produce findings that conform to the defined JSON schema. This module will then be responsible for translating that internal format into the final output:

- JSON/SARIF for agents and CI tools.

- A clean, human-readable table (using a library like tabulate) for interactive use.

By following this plan, we will build a fast, accurate, and highly valuable tool that directly prevents a common class of LLM-induced errors, making the entire llm-cpp-toolkit ecosystem even more effective.
