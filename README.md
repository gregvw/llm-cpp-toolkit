# LLM C++ Toolkit

A comprehensive CLI toolkit designed to help LLMs and AI agents work effectively with C++ and CMake projects. Provides standardized environment checks, context export, code analysis, and repro reduction with JSON outputs optimized for AI consumption.

## 🚀 Quick Start

### Install via npm (Recommended)
```bash
npm install -g llm-cpp-toolkit
llmtk --version
```

### Other Installation Options
- **Homebrew:** `brew tap gregvw/llm-cpp-toolkit && brew install llm-cpp-toolkit`
- **Snap:** `sudo snap install llm-cpp-toolkit`
- **Flatpak:** `flatpak install flathub io.github.gregvw.llm-cpp-toolkit`
- **AppImage:** Download from [releases](https://github.com/gregvw/llm-cpp-toolkit/releases)
- **Script:** `curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash -s -- --yes`

### Basic Usage
```bash
# Check system dependencies
llmtk doctor

# Export project context for LLMs
llmtk context export

# Analyze code with multiple tools
llmtk analyze src/ include/

# Reduce a failing test case
llmtk reduce test.cpp "gcc test.cpp && ./a.out"
```

## 🎯 Key Features

- **🔍 System Health Check** - Verify development tool installation and versions
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