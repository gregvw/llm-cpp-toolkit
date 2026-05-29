# LLM C++ Toolkit

A C++/CMake build intelligence backend for AI coding agents. `llmtk` gives agents deterministic project facts, diagnostics, test results, and dependency metadata through a small CLI and an MCP endpoint. The project is focused on three durable pain points in AI-assisted C++ development:

1. Repeatable C++ tool and environment checks
2. Machine-readable CMake/compile context
3. Structured diagnostics and test output that agents can consume without parsing terminal scrollback

## 🚀 Quick Start

### One-Line Install (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash
llmtk --version
```

### pipx Install (Checksummed Release)
```bash
pipx install llm-cpp-toolkit
llmtk --bootstrap-info      # inspect cached release metadata
```

The pipx package bootstraps a published tarball, verifies its SHA256 sum, and
then executes the toolkit in-place. To work from a local checkout while testing
packaged changes, run `LLMTK_BOOTSTRAP_USE_SOURCE=$PWD llmtk doctor`.

### Development with uv
```bash
uv sync
uv run python cli/llmtk doctor
uv run python -m pytest
uv build --no-sources
```

`uv` is the preferred development and release workflow. Published packages remain standards-compatible so `pipx install llm-cpp-toolkit` continues to work for users who do not have uv installed.

### Alternative Installation Methods
- **Local (no sudo):** `git clone ... && llmtk install --local`
- **Nix:** `nix develop github:gregvw/llm-cpp-toolkit`
- **Docker:** `docker run ghcr.io/gregvw/llm-cpp-toolkit:latest`
- **Homebrew:** `brew tap gregvw/llm-cpp-toolkit && brew install llmtk`

📖 **[Complete Installation Guide](docs/INSTALLATION.md)** | 🚀 **[Quick Start Guide](QUICKSTART.md)** | 🎓 **[Agent Tutorial](docs/TUTORIAL.md)**

## 🚀 90-Second New User Path

1.  **Install `llmtk`**:
    ```bash
    curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash
    ```
2.  **Initialize a project**:
    ```bash
    # Create a new project
    llmtk init my-awesome-project && cd my-awesome-project
    
    # Or adopt an existing one
    # cd path/to/your/project && llmtk init --existing
    ```
3.  **Export build context**:
    ```bash
    llmtk context export
    ```
4.  **Analyze your code**:
    ```bash
    llmtk analyze
    ```

### Basic Usage
```bash
# Bootstrap a new project or adopt an existing one
llmtk init my-cpp-project
llmtk init --existing path/to/existing-project

# Check system dependencies
llmtk doctor

# Export project context for LLMs
llmtk context export
llmtk context export --preview   # Show planned steps without executing
llmtk context export --deep      # Capture targets, toolchains, and preset metadata

# Fast syntax checking before expensive operations
llmtk preflight --diff HEAD~1
llmtk preflight --paths src/ include/ --json exports/preflight.json

# Analyze code with multiple tools
llmtk analyze src/ include/
llmtk analyze --sarif src/  # Generate SARIF output for CI/IDE integration

# Extract dependency graphs
llmtk deps --json --graphviz

# Run tests with structured outputs
llmtk test --json

# Thin compiler diagnostics with context budgets
llmtk stderr-thin --compile main.cpp --level=focused

# Regenerate machine-readable capabilities summary
llmtk capabilities

# Drive the JSON agent loop or expose MCP tools
llmtk agent request '{"requests":[{"id":"caps","kind":"get_capabilities"}]}'
llmtk agent mcp

# Preview any command without side effects
llmtk --dry-run analyze src/

# Opt-in telemetry management (stored locally)
llmtk telemetry status
llmtk telemetry enable
```

### Strict Build Helper

Need a single command that enforces hard warnings, sanitizers, and filtered logs? Use the bundled helper:

```bash
python scripts/strict_build.py full --build build/strict --logs logs/strict --jobs 8
```

This wrapper injects `-Wall -Wextra -Wconversion -Wshadow -Werror`, Address/UB sanitizers, and sensible clang-tidy checks while keeping raw logs under `logs/strict_build/`.

### Project Initialization Options
```bash
# Create projects with custom settings
llmtk init myproject --std=20 --cmake-min=3.25 --preset=library
llmtk init myproject --pic --no-sanitizers --preset=minimal

# Available options:
--std {17,20,23,26}              # C++ standard version
--cmake-min VERSION              # Minimum CMake version
--pic                           # Enable position independent code
--no-sanitizers                 # Disable sanitizer variants
--preset {minimal,full,library} # Project template type
```

When adopting an existing workspace, `llmtk init --existing` also copies any top-level `compile_commands.json` into
`exports/compile_commands.json` so downstream commands and agents can consume it immediately. Every init run also
generates `exports/capabilities.json`, a machine-readable rollup of the manifest-defined tools and commands. The
entire `exports/` directory is ignored by default via `.gitignore`.

## 🎯 Key Features

- **🔍 System Health Check** - Verify development tool installation and versions
- **🧱 Project Bootstrap/Adoption** - Generate starter scaffolding or adopt existing CMake projects with guidance
- **📦 Context Export** - Generate compilation databases and CMake introspection data
- **⚡ Preflight Checks** - Fast syntax and delimiter validation before expensive build operations
- **🔬 Code Analysis** - Run clang-tidy, include-what-you-use, and cppcheck with JSON output
- **📊 Dependency Graphs** - Extract target dependency graphs from CMake codemodel with JSON and Graphviz export
- **🧾 Structured Testing** - Parse CTest results into JSON and SARIF for gating workflows
- **🧠 Deterministic Diagnostics** - Collapse compiler stderr with `llmtk stderr-thin` into budget-aware highlights
- **🔏 Supply-Chain Ready** - pipx bootstrap with checksum enforcement and signed release artifacts
- **🤖 Agent-Optimized** - Stable JSON artifacts and MCP tools designed for AI coding assistants
- **📋 Manifest-Driven** - Tool versions and commands defined in YAML manifests
- **🗂️ Capabilities Summary** - `exports/capabilities.json` captures the toolkit's API surface for agents
- **🛡️ Preview & Privacy Controls** - Global `--dry-run` mode plus opt-in telemetry stored locally

### Supported Agent Surface

The stable v1 agent backend surface is:

- `llmtk doctor`
- `llmtk context export`
- `llmtk preflight`
- `llmtk analyze`
- `llmtk stderr-thin`
- `llmtk test`
- `llmtk deps`
- `llmtk capabilities`
- `llmtk agent mcp`

Planned commands such as `bench`, `reduce`, `diff-context`, `gate`, `format`, `tidy`, and `lsp-bridge` remain in the manifest as non-stable roadmap items until their CLI, docs, tests, and MCP contracts converge.

## 🧪 Sanitizer Variants

Projects created with `llmtk init` include sophisticated sanitizer support with multiple isolated variants:

```bash
# Build different sanitizer combinations
cmake --build build --target myapp_asan_ubsan  # AddressSanitizer + UBSan
cmake --build build --target myapp_tsan        # ThreadSanitizer
cmake --build build --target myapp             # Regular build

# For library projects, both library and example get variants
cmake --build build --target mylib_asan_ubsan
cmake --build build --target mylib_example_asan_ubsan
```

### Sanitizer Features:
- **🎯 Isolated Targets**: Each sanitizer combination gets its own target
- **🔄 No Mutual Exclusion**: Can build AddressSanitizer and ThreadSanitizer variants simultaneously
- **📁 Shared Dependencies**: Sanitized variants mirror all include paths and compile options
- **⚡ Smart Building**: Use `EXCLUDE_FROM_ALL` to avoid building variants by default
- **🏗️ Complete Coverage**: Works for both executables and libraries

### Preset-Specific Behavior:
- **`--preset=full`**: Includes sanitized variants of main executable
- **`--preset=library`**: Includes sanitized variants of both library and example
- **`--preset=minimal`**: No sanitizer complexity (basic executable only)
- **`--no-sanitizers`**: Completely disables all sanitizer setup

## ⚡ Preflight Checks

llmtk includes fast preflight validation to catch common syntax and delimiter errors before expensive compilation. This is especially valuable for catching LLM-induced errors quickly.

### Supported File Types:
- **C/C++**: Full clang syntax checking with compile_commands.json integration
- **JSON**: Python json module + optional jq validation
- **YAML**: PyYAML parser + optional yamllint style checks
- **TOML**: Python tomllib/tomli + optional taplo validation
- **Shell**: bash -n syntax + optional shellcheck static analysis
- **CMake**: cmake parser + optional cmake-format validation

### Usage Examples:
```bash
# Check files changed since last commit
llmtk preflight --diff HEAD~1

# Check specific paths
llmtk preflight --paths src/ include/ CMakeLists.txt

# Check with structured output
llmtk preflight --diff HEAD --json exports/preflight.json --sarif exports/preflight.sarif

# Strict mode (treat warnings as errors)
llmtk preflight --paths . --strict

# Filter by file types
llmtk preflight --diff HEAD --extensions .cpp .h .json
```

### Output Formats:
- **Human-readable**: Clean table format with file paths, locations, and messages
- **JSON**: Structured findings with comprehensive statistics and rule breakdowns
- **SARIF 2.1.0**: CI-ready format with rich rule descriptions and metadata

### Integration with Build Workflows:
```bash
# Pre-build validation
llmtk preflight --diff HEAD || exit 1
llmtk analyze src/
cmake --build build
```

## 📁 Output Structure

All artifacts are written to the `exports/` directory:

```
exports/
├── doctor.json              # System dependency report
├── capabilities.json        # Toolkit commands/tools summary for agents
├── context.json             # Project context summary
├── compile_commands.json    # Compilation database
├── init-existing.json       # Project adoption report (--existing only)
├── cmake-file-api/         # CMake introspection data
├── reports/                # Analysis reports
│   ├── clang-tidy.json
│   ├── iwyu.json
│   ├── cppcheck.json
│   ├── analysis.sarif      # Merged SARIF from all analyzers (--sarif flag)
│   ├── preflight.json      # Fast syntax check results
│   └── preflight.sarif     # SARIF format for CI integration
├── tests/                  # Structured CTest exports
│   ├── ctest_results.json
│   ├── ctest_results.sarif
│   ├── Test.xml
│   └── ctest_stdout.txt
├── diagnostics/            # Deterministic stderr thinning outputs
│   ├── stderr-thin.json
│   ├── stderr-thin.txt
│   └── stderr-raw.txt
└── repros/                 # Reduced test cases
    ├── minimized.cpp
    └── report.json
```

The `capabilities.json` file is automatically generated during `llmtk init` and `llmtk capabilities` commands, providing a machine-readable summary of all available tools and commands for AI agents to consume.

## 🛠️ Supported Tools

### Core Tools
- **Build:** cmake, ninja, bear
- **Analysis:** clangd, clang-tidy, clang-format, include-what-you-use, cppcheck
- **Utilities:** rg, fd, jq, yq, ccache/sccache, mold/lld

### Optional Tools
- **Navigation:** fzf, zoxide, bat, universal-ctags
- **Performance:** tokei, hyperfine, entr/watchexec
- **System:** eza/tree/procs/bottom, httpie/xh, tldr/cheat

## 📚 Documentation

- **[Quickstart Guide](docs/QUICKSTART.md)** - Get up and running quickly
- **[Full Documentation](docs/README.md)** - Complete toolkit overview
- **[Tool Reference](docs/REFERENCE.md)** - Auto-generated from manifests
- **[Distribution Guide](DISTRIBUTION.md)** - Building and packaging
- **[Privacy & Telemetry](docs/PRIVACY.md)** - Data collection policy and opt-in controls

## 🔐 Release Integrity

- `scripts/release/check_version_pins.py` ensures that Homebrew, Nix, Docker, and
  release manifests target the same toolkit version in `VERSION`.
- `scripts/release/sign_artifacts.py` produces `SHA256SUMS` (and optional GPG
  signatures) for the contents of `dist/` or any artifact directory.
- `src/llmtk_bootstrap/data/releases.json` records the tarball URL and checksum
  consumed by the pipx bootstrapper; update it for every tagged release.

## 🏗️ Architecture

The toolkit follows a manifest-driven architecture:

- **`manifest/tools.yaml`** - Tool versions, checks, and capabilities
- **`manifest/commands.yaml`** - Command definitions and outputs
- **`cli/llmtk`** - Python CLI entry point
- **`modules/`** - Tool adapter scripts
- **`presets/`** - Configuration templates
- **`docs/AGENT_COLLABORATION.md`** - Planner/implementer/reviewer protocol for Codex and Claude

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Update manifests if adding tools/commands
5. Run `llmtk docs` to regenerate documentation
6. Submit a pull request

## 📦 Building Packages

```bash
# Build all distribution packages
./build-packages.sh --all

# Build specific packages
./build-packages.sh --npm --appimage
```

## 📄 License

BSD-3-Clause License - see [LICENSE](LICENSE) file for details.
