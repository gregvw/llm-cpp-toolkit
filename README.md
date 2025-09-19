# LLM C++ Toolkit

A comprehensive CLI toolkit designed to help LLMs and AI agents work effectively with C++ and CMake projects. Provides standardized environment checks, context export, code analysis, and repro reduction with JSON outputs optimized for AI consumption.

## 🚀 Quick Start

### One-Line Install (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash
llmtk --version
```

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

# Analyze code with multiple tools
llmtk analyze src/ include/

# Thin compiler diagnostics with context budgets
llmtk stderr-thin --compile main.cpp --level=focused

# Regenerate machine-readable capabilities summary
llmtk capabilities

# Reduce a failing test case
llmtk reduce test.cpp "gcc test.cpp && ./a.out"
```

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
- **🔬 Code Analysis** - Run clang-tidy, include-what-you-use, and cppcheck with JSON output
- **🧠 Deterministic Diagnostics** - Collapse compiler stderr with `llmtk stderr-thin` into budget-aware highlights
- **🧪 Advanced Sanitizer Support** - Multiple sanitizer variants with proper isolation
- **🪚 Test Case Reduction** - Minimize failing code with cvise integration
- **🤖 LLM-Optimized** - JSON outputs designed for AI agent consumption
- **📋 Manifest-Driven** - Tool versions and commands defined in YAML manifests
- **🗂️ Capabilities Summary** - `exports/capabilities.json` captures the toolkit's API surface for agents

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
│   └── cppcheck.json
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

## 🏗️ Architecture

The toolkit follows a manifest-driven architecture:

- **`manifest/tools.yaml`** - Tool versions, checks, and capabilities
- **`manifest/commands.yaml`** - Command definitions and outputs
- **`cli/llmtk`** - Python CLI entry point
- **`modules/`** - Tool adapter scripts
- **`presets/`** - Configuration templates

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

## 🙏 Acknowledgments

This toolkit is designed to work seamlessly with Large Language Models and AI coding assistants, providing the structured data they need to effectively analyze and work with C++ codebases.
