# Quickstart

## Installation

Choose your preferred installation method:

### Python Development (uv)
```bash
uv sync
uv run python cli/llmtk doctor
```

### Quick Install (isolated Python)
```bash
uv tool install llm-cpp-toolkit
# or: pipx install llm-cpp-toolkit
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

# Run fast validation and structured tests
llmtk preflight --paths src/ include/ --json exports/reports/preflight.json
llmtk test --json

# Expose the stable C++ workflow to MCP-capable agents
llmtk agent mcp
```

Over MCP, agents can call the individual commands as tools (`llmtk.context_export`,
`llmtk.preflight`, `llmtk.test`, `llmtk.deps`, `llmtk.capabilities`, …) or the
high-level `llmtk.agent_prepare` tool, which runs capabilities, doctor, context
export, and preflight (plus an optional CTest step) in one call and returns a
compact status with artifact paths, warnings, and recommended next actions.

## Development Usage

If working from the repo directly:
```bash
python3 cli/llmtk doctor
python3 cli/llmtk context export --build build
python3 cli/llmtk preflight --paths src/ include/
python3 cli/llmtk analyze src/ include/
```

## Output

All artifacts are written under `exports/` directory for easy parsing by LLMs and agents:
- `exports/doctor.json` - System dependency report
- `exports/context.json` - Project context summary
- `exports/compile_commands.json` - Compilation database
- `exports/cmake-file-api/` - CMake introspection data
- `exports/reports/` - Analysis and preflight reports
- `exports/tests/` - CTest JSON/SARIF summaries
- `exports/diagnostics/` - Thinned compiler stderr reports
- `exports/dependency_graphs/` - Target dependency graphs (`llmtk deps`)
