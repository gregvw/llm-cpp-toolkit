# Quickstart

## Installation

Choose your preferred installation method:

### Quick Install (npm)
```bash
npm install -g llm-cpp-toolkit
llmtk --version
```

### Other Methods
- **Homebrew:** `brew tap gregvw/llm-cpp-toolkit && brew install llm-cpp-toolkit`
- **Snap:** `sudo snap install llm-cpp-toolkit`
- **Flatpak:** `flatpak install flathub io.github.gregvw.llm-cpp-toolkit`
- **AppImage:** Download from [releases](https://github.com/gregvw/llm-cpp-toolkit/releases)
- **Script:** `curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash -s -- --yes`

## Basic Usage

After installation, ensure core tools exist: `cmake`, `ninja` (others optional).

```bash
# Check system dependencies
llmtk doctor

# Export project context for LLMs
llmtk context export --build build

# Analyze code with multiple tools
llmtk analyze src/ include/

# Reduce a failing test case
llmtk reduce test.cpp "gcc test.cpp && ./a.out"
```

## Development Usage

If working from the repo directly:
```bash
python3 cli/llmtk doctor
python3 cli/llmtk context export --build build
python3 cli/llmtk analyze src/ include/
```

## Output

All artifacts are written under `exports/` directory for easy parsing by LLMs and agents:
- `exports/doctor.json` - System dependency report
- `exports/context.json` - Project context summary
- `exports/compile_commands.json` - Compilation database
- `exports/cmake-file-api/` - CMake introspection data
- `exports/reports/` - Analysis reports (clang-tidy, IWYU, cppcheck)
- `exports/repros/` - Reduced test cases

