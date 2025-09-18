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

📖 **[Complete Installation Guide](docs/INSTALLATION.md)** | 🚀 **[Quick Start Guide](QUICKSTART.md)**

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

# Reduce a failing test case
llmtk reduce test.cpp "gcc test.cpp && ./a.out"
```

When adopting an existing workspace, `llmtk init --existing` also copies any top-level `compile_commands.json` into
`exports/compile_commands.json` so downstream commands and agents can consume it immediately.

## 🎯 Key Features

- **🔍 System Health Check** - Verify development tool installation and versions
- **🧱 Project Bootstrap/Adoption** - Generate starter scaffolding or adopt existing CMake projects with guidance
- **📦 Context Export** - Generate compilation databases and CMake introspection data
- **🔬 Code Analysis** - Run clang-tidy, include-what-you-use, and cppcheck with JSON output
- **🪚 Test Case Reduction** - Minimize failing code with cvise integration
- **🤖 LLM-Optimized** - JSON outputs designed for AI agent consumption
- **📋 Manifest-Driven** - Tool versions and commands defined in YAML manifests

## 📁 Output Structure

All artifacts are written to the `exports/` directory:

```
exports/
├── doctor.json              # System dependency report
├── context.json             # Project context summary
├── compile_commands.json    # Compilation database
├── cmake-file-api/         # CMake introspection data
├── reports/                # Analysis reports
│   ├── clang-tidy.json
│   ├── iwyu.json
│   └── cppcheck.json
└── repros/                 # Reduced test cases
    ├── minimized.cpp
    └── report.json
```

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
