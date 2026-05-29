# LLM C++ Toolkit

This repository provides a C++/CMake build intelligence backend for AI coding agents. It standardizes environment checks, CMake context export, diagnostics, dependency graphs, and CTest summaries with JSON outputs and a stable MCP surface.

The content below mirrors the project instructions maintained for agents in `AGENTS.md`, adapted as user-facing documentation.

## Overview

The goal is to provide deterministic C++ project facts to agents that otherwise have to infer build state from noisy terminal output. Generic editor/file/Git operations are secondary to C++ build intelligence.

## Detailed Goal

1) One repo with:
- A machine‑readable manifest describing tools, versions, commands, and how to parse outputs.
- A tiny wrapper CLI (`llmtk`) that checks, exports, diagnoses, and exposes consistent subcommands.
- Multiple installation paths: Nix flake, Linuxbrew tap, Docker/DevContainer, and a zero‑dependency Bash installer.
- Docs auto‑generated from the manifest for humans and a compact `capabilities.json` for agents.
- “Context pack” commands to export artifacts LLMs thrive on (compile DB, CMake JSON, logs).

2) LLM/agent‑friendly conventions:
- Every subcommand supports JSON output (or writes JSON to a file) for easy parsing.
- Deterministic versions pinned in one place.
- A `llmtk context export` that gathers canonical inputs (e.g., `compile_commands.json`, sanitizer logs, perf traces).

3) Standard compilation tools (`manifest/tools.yaml`) and command wiring (`manifest/commands.yaml`).

Example tool manifest entries:

```yaml
schema: 1
tools:
  clangd:
    version: "18.1.8"
    provides: ["lsp", "xref", "refactor"]
    check:
      cmd: ["clangd", "--version"]
      expect: "clangd version 18"
  mold:
    version: "2.32.0"
    provides: ["linker"]
    check:
      cmd: ["mold", "--version"]
  cvise:
    version: "2.9.0"
    provides: ["reducer"]
    check:
      cmd: ["cvise", "--version"]
```

Example command manifest entries:

```yaml
schema: 1
commands:
  context-export:
    description: Collects artifacts LLMs rely on.
    runs: ["modules/compile_db.sh", "modules/cmake_introspect.sh"]
    outputs:
      - "exports/compile_commands.json"
      - "exports/cmake-file-api/*.json"
    json_summary: "exports/context.json"
  analyze:
    description: Run clang-tidy + IWYU + cppcheck with JSON reports.
    args:
      - name: paths
        variadic: true
    runs: ["modules/analyze.sh"]
    outputs:
      - "exports/reports/clang-tidy.json"
      - "exports/reports/iwyu.json"
      - "exports/reports/cppcheck.json"
  test:
    status: supported
    description: Run CTest suites and emit structured results.
    outputs:
      - "exports/tests/ctest_results.json"
      - "exports/tests/ctest_results.sarif"
```

4) Build management: a Python script (`build_manager`) that configures, builds, and tests with strict flags (`-Werror -Wall -Wextra -Wconversion -Wshadow`), sanitizer support (`-fsanitize=undefined,address`), and sensible clang‑tidy defaults, while producing concise, LLM‑friendly summaries.

## Repo Layout

```
llm-cpp-toolkit/
├─ manifest/                    # single source of truth
│  ├─ tools.yaml                # versions, checks
│  └─ commands.yaml             # subcommands, outputs
├─ cli/
│  └─ llmtk                     # small Python entry point
├─ modules/                     # thin adapters around tools
│  ├─ cmake_introspect.sh
│  ├─ compile_db.sh
│  ├─ analyze.sh                # orchestration for analyzers
├─ presets/
│  ├─ .clang-tidy
│  └─ .clang-format
├─ docs/
│  ├─ README.md                 # this file
│  └─ QUICKSTART.md
└─ exports/                     # default output dir for context packs
```

## Tooling Tiers

- Core: `cmake`, `ninja`, `bear`, `clangd`, `clang-format`, `clang-tidy`, `rg`, `fd`, `jq`, `yq`, `ccache`/`sccache`, `mold`/`lld`.
- Recommended: `fzf`, `zoxide`, `bat`, `universal-ctags`, `include-what-you-use`, `cppcheck`, `tokei`, `hyperfine`, `entr`/`watchexec`, `pre-commit` presets.
- Optional: `eza`/`tree`/`procs`/`bottom`, `httpie`/`xh`, `tldr`/`cheat`, `difftastic`/`delta`.

## Why CLI‑first

- Agent‑agnostic, deterministic, portable, and testable. The CLI does the work; agents orchestrate and summarize.

## What to build (current status)

- `llmtk doctor` – machine‑readable health report (exports/doctor.json).
- `llmtk context export` – emits compile DB + CMake File API (exports/context.json).
- `llmtk analyze` – runs clang‑tidy/IWYU/cppcheck → JSON reports.
- `llmtk preflight` – fast syntax/config checks before expensive builds.
- `llmtk stderr-thin` – compacts compiler stderr into budget-aware diagnostics.
- `llmtk test` – CTest JSON/SARIF summaries.
- `llmtk deps` – CMake target dependency graph exports.
- `llmtk agent mcp` – MCP tools for the stable C++ workflow.
- Planned commands remain in the manifest with `status: planned` until their CLI, docs, tests, and MCP contracts converge.

## Quickstart

See `docs/QUICKSTART.md` for command examples. Artifacts land under `exports/` for easy parsing.

Check version:

```
llmtk --version
```

## Installation

The LLM C++ Toolkit can be installed through multiple package managers and distribution methods:

### Package Managers (Recommended)

#### npm (Cross-platform)
```bash
# Install globally
npm install -g llm-cpp-toolkit

# Or use directly without installing
npx llm-cpp-toolkit --version
```

#### Homebrew (macOS/Linux)
```bash
# Add the tap and install
brew tap gregvw/llm-cpp-toolkit
brew install llm-cpp-toolkit
```

#### Snap (Linux)
```bash
# Install from Snap Store
sudo snap install llm-cpp-toolkit

# Run the tool
llmtk --version
```

#### Flatpak (Linux)
```bash
# Install from Flathub
flatpak install flathub io.github.gregvw.llm-cpp-toolkit

# Run the tool
flatpak run io.github.gregvw.llm-cpp-toolkit --version
```

### Portable/Manual Installation

#### AppImage (Linux)
```bash
# Download the latest AppImage from releases
wget https://github.com/gregvw/llm-cpp-toolkit/releases/latest/download/llm-cpp-toolkit-x86_64.AppImage
chmod +x llm-cpp-toolkit-x86_64.AppImage
./llm-cpp-toolkit-x86_64.AppImage --version
```

#### One-line Script Install
Installs to `~/.local/share/llm-cpp-toolkit` with wrapper at `~/.local/bin/llmtk`:

```bash
curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash -s -- --yes
```

Options:
- `--prefix DIR` - Change wrapper prefix (default `~/.local`)
- `--dir DIR` - Change install directory (default `~/.local/share/llm-cpp-toolkit`)
- `--no-deps` - Skip package manager dependency installation
- `--branch BRANCH` - Install from specific git branch

After script installation, ensure `~/.local/bin` is in your `PATH`.

### Verifying Installation

After installation with any method:
```bash
llmtk --version
llmtk doctor  # Check system dependencies
```

See `DISTRIBUTION.md` for detailed build and packaging instructions.

## Reference

- See `docs/REFERENCE.md` for an auto-generated list of tools and commands derived from the manifests.
- Try `docs/TUTORIAL.md` for a step-by-step walkthrough that pairs the toolkit with an agent-driven debug loop.

### Keeping Docs in Sync

`docs/REFERENCE.md` is derived from the YAML manifests under `manifest/`
(`tools.yaml`, `commands.yaml`). Update it whenever you change those manifests so
the reference stays accurate.
