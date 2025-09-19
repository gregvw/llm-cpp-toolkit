# Overview

The goal is to create an extensive common CLI toolkit of utilities that would aid an LLM in C++ development
on a Linux or MacOS system that can be easily and broadly shared with other users wishing to improve the
performance and efficiency of their AI coding assistants. 

## Detailed Goal

1. One repo (e.g., llm-cpp-toolkit/) with:
- A machine-readable manifest describing tools, versions, commands, and how to parse outputs.
- A tiny wrapper CLI (llmtk) that installs, checks, and exposes consistent subcommands.
- Multiple installation paths: Nix flake, Linuxbrew tap, Docker/DevContainer, and a zero-dependency Bash installer.
- Docs auto-generated from the manifest for humans and a compact capabilities.json for agents.
- “Context pack” commands to export artifacts LLMs thrive on (compile DB, CMake JSON, logs).

2. LLM/agent friendly conventions:
- Every subcommand supports `--json` (or writes JSON to a file) for easy parsing.
- Deterministic versions pinned in one place.
- A llmtk context export that gathers canonical inputs (e.g., `compile_commands.json`, sanitizer logs, perf traces). 

3. Standard compilation tools (`manifest/tools.yml`) 
```yaml
schema: 1
tools:
  clangd:
    version: "18.1.8"
    provides: ["lsp", "xref", "refactor"]
    install:
      apt: ["clangd-18"]
      dnf: ["clang-tools-extra"]
      pacman: ["clang"]
      brew:  ["llvm@18"]
      nix:   ["clang-tools_18"]
    check:
      cmd: ["clangd", "--version"]
      expect: "clangd version 18"
  mold:
    version: "2.32.0"
    provides: ["linker"]
    install:
      apt: ["mold"]
      dnf: ["mold"]
      pacman: ["mold"]
      brew:  ["mold"]
      nix:   ["mold"]
    check:
      cmd: ["mold", "--version"]
  cvise:
    version: "2.9.0"
    provides: ["reducer"]
    install:
      apt: ["cvise"]
      dnf: ["cvise"]
      pacman: ["cvise"]
      brew:  ["cvise"]
      nix:   ["cvise"]
  # ... add clang-tidy, clang-format, iwyu, cppcheck, cmake, ninja, ccache, ripgrep, fd, bloaty ...
```

```yaml
schema: 1
commands:
  context-export:
    description: Collects artifacts LLMs rely on.
    runs: ["modules/compile_db.sh", "modules/cmake_introspect.sh"]
    outputs:
      - "exports/compile_commands.json"
      - "exports/cmake-file-api/*.json"
    json_summary: "exports/context.json"   # machine-readable rollup
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
  reduce:
    description: Minimize a failing repro with cvise.
    args:
      - {name: input, required: true}
      - {name: test_cmd, required: true}
    runs: ["modules/reduce.sh"]
    outputs:
      - "exports/repros/minimized.cpp"
      - "exports/repros/report.json"
```

4. Make a Python script for managing CMake configure, building and testing with a single command that 
   also enforces strict standard compilation settings: `-Werror -Wall -Wextra -Wconversions -Wshadow` 
   Use address sanitizer and undefined behavior sanitizer ( `-fsanitize=undefined` and
   `-fsanitize=address`) and sensible `clang-tidy` checks (e.f. core guidelines).
   See `build_manager` as an example to work from. This also makes it possible to filter out 
   unnecessary output from the compiler, cmake, ctest, etc that only consume context helping the 
   agent identify problems. 


## Possible Repo Layout
```
    llm-cpp-toolkit/
    ├─ manifest/                    # single source of truth
    │  ├─ tools.yaml                # versions, install recipes, health checks
    │  └─ commands.yaml             # subcommands, arguments, outputs, examples
    ├─ cli/
    │  └─ llmtk                     # small Python or Bash entry point
    ├─ installers/
    │  ├─ install.sh                # distro-agnostic installer (Apt/Yum/Dnf/Pacman)
    │  ├─ brew/Formula/llmtk.rb     # Linuxbrew formula (pins versions)
    │  └─ nix/flake.nix             # reproducible env (best for CI/teammates)
    ├─ containers/
    │  ├─ Dockerfile
    │  └─ devcontainer.json
    ├─ modules/                     # thin adapters around tools
    │  ├─ cmake_introspect.sh
    │  ├─ compile_db.sh
    │  ├─ reduce.sh                 # cvise wrappers
    │  ├─ analyze.sh                # clang-tidy, iwyu, cppcheck orchestration
    │  ├─ perf_collect.sh
    │  └─ size_bloat.sh             # bloaty, readelf, etc.
    ├─ presets/
    │  ├─ .clang-tidy
    │  ├─ .clang-format
    │  ├─ cmake-format.yaml
    │  └─ pre-commit-config.yaml
    ├─ docs/
    │  ├─ README.md
    │  ├─ QUICKSTART.md
    │  └─ REFERENCE.md              # auto-generated from manifest
    └─ exports/                     # default output dir for context packs
```

## Suggested Tools 

### File Search & Navigation

-   **ripgrep (`rg`)**: A very fast, recursive search tool that respects `.gitignore` by default. (Gemini, ChatGPT, Claude)
-   **fd-find (`fd`)**: A simple, fast, and user-friendly alternative to `find` with sensible defaults. (Gemini, ChatGPT, Claude)
-   **fzf**: A general-purpose command-line fuzzy finder for interactive filtering. (Gemini, ChatGPT, Claude)
-   **zoxide**: A "smarter `cd` command" that learns your most used directories. (Gemini, ChatGPT)
-   **bat**: A `cat` clone with syntax highlighting, Git integration, and automatic paging. (Gemini, ChatGPT, Claude)
-   **exa** / **eza** / **lsd**: Modern replacements for `ls` with more information, colors, and icons. (Gemini, Claude)
-   **tree**: A tool for visualizing directory structures. (Claude)

### Code & Text Processing

-   **sd**: An intuitive find-and-replace command-line tool (alternative to `sed`). (Gemini, ChatGPT, Claude)
-   **jq**: A lightweight and flexible command-line JSON processor. (Gemini, ChatGPT, Claude)
-   **yq**: A command-line processor for YAML, JSON, and XML (a `jq` equivalent). (Gemini, ChatGPT, Claude)
-   **dasel**: A query and conversion tool for JSON, YAML, TOML, XML, and CSV. (ChatGPT)
-   **jless**: An interactive JSON viewer with search and folding capabilities. (ChatGPT)
-   **gron**: A tool that makes JSON greppable by transforming it into discrete assignments. (ChatGPT)
-   **miller (`mlr`)**: A powerful tool for processing CSV, TSV, and JSON data. (ChatGPT, Claude)
-   **choose**: A human-friendly alternative to `cut` for selecting columns of text. (Claude)
-   **renameutils**: A set of tools for safer and easier batch renaming of files. (ChatGPT)

### Linting, Formatting, & Code Quality

-   **shellcheck**: A static analysis tool that finds common bugs in shell scripts. (Gemini, ChatGPT, Claude)
-   **shfmt**: An autoformatter for shell scripts to maintain a consistent style. (Gemini, ChatGPT)
-   **yamllint**: A linter for checking YAML file style and syntax. (ChatGPT, Claude)
-   **hadolint**: A linter for Dockerfiles that enforces best practices. (ChatGPT, Claude)
-   **markdownlint-cli**: A command-line interface for the Markdown linting library. (Claude)
-   **clang-format**: An autoformatter for C, C++, Objective-C, and Protobuf code. (ChatGPT)
-   **clang-tidy**: A C/C++ linter and static analysis tool with fix-its. (ChatGPT)
-   **black**: An opinionated and widely used autoformatter for Python code. (ChatGPT)
-   **ruff**: An extremely fast linter and fixer for Python code. (ChatGPT)
-   **prettier**: An opinionated code formatter for web development languages and file formats. (ChatGPT)
-   **codespell**: A tool to find and fix common spelling mistakes in source code. (ChatGPT)

### Git & Version Control

-   **delta** / **git-delta**: A syntax-highlighting pager for `git`, `diff`, and `grep` output. (Gemini, ChatGPT, Claude)
-   **difftastic**: A structural diff tool that understands code syntax. (ChatGPT)
-   **icdiff**: A tool for side-by-side, colored diffs in the terminal. (ChatGPT)
-   **git-extras**: A collection of useful command-line aliases for Git. (ChatGPT)
-   **lazygit**: A terminal-based user interface for Git operations. (Claude)
-   **gh**: The official GitHub command-line tool for managing PRs, issues, and more. (Claude)
-   **tig**: A text-mode interface for browsing Git repositories. (Claude)

### Build, Benchmarking, & Code Intelligence

-   **hyperfine**: A command-line benchmarking tool with statistical analysis. (Gemini, ChatGPT, Claude)
-   **tokei**: A tool that displays statistics about your code (lines, files, comments). (Gemini, ChatGPT, Claude)
-   **universal-ctags**: A tool for generating language-aware index files for code navigation. (ChatGPT)
-   **bear**: A tool that generates a `compile_commands.json` file for use with other tools like `clangd`. (ChatGPT)
-   **ninja**: A small, fast build system backend. (ChatGPT)
-   **ccache**: A compiler cache that speeds up recompilation by caching previous results. (ChatGPT)
-   **sccache**: A compiler cache with support for remote/distributed backends. (ChatGPT)

### Automation & Watching

-   **entr**: A utility to run arbitrary commands when files change. (ChatGPT)
-   **watchexec**: A cross-platform file watcher with advanced filtering and ignore support. (ChatGPT)
-   **just**: A simple command runner, often used as a `make` alternative. (ChatGPT)
-   **task**: A modern task runner and build tool that uses a YAML configuration file. (ChatGPT)
-   **pre-commit**: A framework for managing and maintaining multi-language pre-commit hooks. (ChatGPT)

### HTTP & APIs

-   **httpie**: A human-friendly HTTP client with a focus on usability and pretty-printing. (ChatGPT, Claude)
-   **xh**: A fast and minimal `httpie`-like client written in Rust. (ChatGPT)

### System & Process Monitoring

-   **procs**: A modern replacement for `ps` with a tree view and more readable output. (ChatGPT)
-   **bottom**: A graphical process and system monitor for the terminal. (ChatGPT)
-   **duf**: A more readable and user-friendly tool for checking disk usage/free space. (ChatGPT)
-   **dust**: An intuitive `du` alternative that provides a visual representation of disk usage. (ChatGPT)

### Documentation & Reference

-   **tldr**: A collection of community-driven, concise examples for command-line tools. (ChatGPT, Claude)
-   **cheat**: A tool for creating and viewing your own interactive cheatsheets. (ChatGPT)

### Data & File Formats

-   **xsv**: A fast command-line toolkit for working with CSV data. (ChatGPT)
-   **ripgrep-all (`rga`)**: A tool that extends `ripgrep` to search inside PDFs, E-Books, Office documents, and more. (ChatGPT)


## Tier System 

Not all tools are equally critical for LLM workflows. 

### **Core (always installed)**

Essential for C++/CMake + LLM workflows:

* `cmake`, `ninja`, `bear`
* `clangd`, `clang-format`, `clang-tidy`
* `ripgrep`, `fd`, `jq`, `yq`
* `ccache` or `sccache`
* `mold` (or `lld`)

### **Recommended (LLM amplifiers)**

Tools that make code review, context extraction, and patching more effective:

* `fzf`, `zoxide`, `bat`
* `universal-ctags`
* `include-what-you-use`
* `cppcheck`
* `tokei`
* `hyperfine`
* `entr` / `watchexec`
* `pre-commit` + presets (`clang-format`, `codespell`, `cmake-format`)

### **Optional (ergonomics & ecosystem)**

Nice-to-have for teams, not required for agents:

* `exa`/`eza`, `tree`, `procs`, `bottom`
* `httpie`/`xh`
* `tldr`, `cheat`
* `difftastic`, `delta`

## Guidance 

Short answer: **yes—build this as a CLI-first toolkit** and let Codex/CLI agents (or any LLM) call it. That’s the easiest path to something reliable, shareable, and agent-agnostic.

## Why CLI-first is easier (and better)

* **Agent-agnostic:** Any LLM/agent can run `llmtk analyze …` and parse JSON—no SDK lock-in.
* **Deterministic & testable:** You can script, unit test, and CI the CLI. Prompts… not so much.
* **Portable installs:** Ship Nix/Brew/Docker/**bash** installer once; everyone’s environment stays sane.
* **Separation of concerns:** The CLI does work; the agent just orchestrates and summarizes.

## What to build

* A tiny wrapper, e.g. `llmtk`, with subcommands:

  * `llmtk install` – installs deps from a manifest.
  * `llmtk init` – scaffolds new projects or emits adoption reports for existing ones (copying existing compile DBs into exports and refreshing `exports/capabilities.json`).
  * `llmtk doctor` – prints a machine-readable health report.
  * `llmtk context export` – emits `compile_commands.json` + CMake File API JSON.
* `llmtk analyze` – runs clang-tidy/IWYU/cppcheck → JSON reports.
* `llmtk reduce` – cvise wrapper to minimize repros.
* `llmtk capabilities` – regenerate the manifest-driven `exports/capabilities.json` summary.
* `llmtk stderr-thin` – collapse compiler stderr into structured, budget-aware highlights for agents.

`llmtk stderr-thin` always emits three artifacts under `exports/diagnostics/`:

- `stderr-thin.txt` – the context-budgeted view at the requested tier (`summary`, `focused`, or `detailed`).
- `stderr-thin.json` – structured metadata with severity counts, highlights, and the underlying diagnostic payload.
- `stderr-raw.txt` – the untouched stderr capture for deep dives when more context is explicitly requested.

Provide either a stored log (`--log`), a compile database entry (`--compile` or `--compile-index`), or a command to run (`-- …`).
Every invocation accepts `--context-budget` to bound token usage, and agents should default to `--level=focused` for interactive fix-it loops.
* **Outputs** always land under `exports/` and include at least one JSON file per command.
* A **manifest** (YAML) drives installs, versions, and docs generation.
* Optional adapters for agents/editors later (but the CLI is the source of truth).

## Minimal starter you can drop in today

Here’s a super-small Python entry point you can extend. It shows the pattern: subcommands + JSON output + zero surprises.

```python
#!/usr/bin/env python3
# file: llmtk
import argparse, json, os, subprocess, sys, shutil, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
EXPORTS.mkdir(exist_ok=True)

def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout

def cmd_doctor(_):
    tools = ["cmake","ninja","clangd","clang-tidy","clang-format","rg","fd","jq"]
    report = {}
    for t in tools:
        path = shutil.which(t)
        report[t] = {"found": bool(path), "path": path or None}
        if path:
            try:
                ver = run([t, "--version"]).splitlines()[0][:200]
            except Exception:
                ver = None
            report[t]["version"] = ver
    out = EXPORTS / "doctor.json"
    out.write_text(json.dumps(report, indent=2))
    print(str(out))

def cmd_context_export(args):
    build = pathlib.Path(args.build)
    build.mkdir(exist_ok=True)
    # compile_commands.json
    run(["cmake","-S",".","-B",str(build),"-G","Ninja","-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"])
    (EXPORTS / "compile_commands.json").write_bytes((build/"compile_commands.json").read_bytes())
    # CMake File API codemodel
    q = build/".cmake/api/v1/query"; q.mkdir(parents=True, exist_ok=True)
    (q/"codemodel-v2").write_text("")
    try:
        run(["cmake","--build",str(build),"-j"])
    except Exception:
        pass  # building optional here
    reply = build/".cmake/api/v1/reply"
    if reply.exists():
        (EXPORTS/"cmake-file-api").mkdir(exist_ok=True)
        for p in reply.iterdir():
            (EXPORTS/"cmake-file-api"/p.name).write_bytes(p.read_bytes())
    summary = {
        "compile_commands": "exports/compile_commands.json",
        "cmake_file_api": "exports/cmake-file-api/",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat()
    }
    (EXPORTS/"context.json").write_text(json.dumps(summary, indent=2))
    print(str(EXPORTS/"context.json"))

def cmd_analyze(args):
    reports = EXPORTS/"reports"; reports.mkdir(exist_ok=True)
    paths = args.paths or ["src","include","."]
    # clang-tidy YAML -> JSON (simple passthrough if jq exists)
    tidy_yaml = run(["clang-tidy","-p","exports/compile_commands.json","-dump-config"])  # placeholder
    (reports/"clang-tidy.json").write_text(json.dumps({"note":"wire real invocation","config":tidy_yaml}, indent=2))
    (reports/"iwyu.json").write_text(json.dumps({"note":"invoke iwyu via compile_commands"}, indent=2))
    (reports/"cppcheck.json").write_text(json.dumps({"note":"run cppcheck --project exports/compile_commands.json"}, indent=2))
    print(str(reports))

def main():
    ap = argparse.ArgumentParser(prog="llmtk")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    cx = sub.add_parser("context", help="context commands").add_subparsers(dest="sub", required=True)
    cx_exp = cx.add_parser("export"); cx_exp.add_argument("--build", default="build"); cx_exp.set_defaults(fn=cmd_context_export)
    an = sub.add_parser("analyze"); an.add_argument("paths", nargs="*"); an.set_defaults(fn=cmd_analyze)
    args = ap.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()
```

Usage:

```bash
chmod +x llmtk
./llmtk doctor            # writes exports/doctor.json
./llmtk context export    # writes compile_commands + cmake-file-api + context.json
./llmtk analyze           # stub reports -> expand as you wire real tools
```

From here you can:

* Swap stubs with real invocations (clang-tidy with `-export-fixes`, IWYU parsing, cppcheck XML→JSON).
* Add `install` and `doctor --fix` that read a `tools.yaml` and install via apt/dnf/pacman/brew/nix.
* Layer a Nix flake / Brew formula / Dockerfile for easy distribution.

## How an agent (Codex, etc.) would use it

* Ask user to run `llmtk context export`.
* Read `exports/context.json` to discover where everything lives.
* Run `llmtk analyze src/ include/` and parse `exports/reports/*.json`.
* Propose patches, then optionally `llmtk reduce repro.cpp -- test.sh` to shrink a failing case.

### Example Contracts

#### `llmtk doctor`

An agent can use the `doctor` command to verify the user's environment.

**Command**:
```bash
llmtk doctor
```

**Output (`exports/doctor.json`)**:
```json
{
  "clangd": {
    "found": true,
    "path": "/usr/bin/clangd",
    "version_line": "clangd version 18.1.8"
  },
  "cmake": {
    "found": true,
    "path": "/usr/bin/cmake",
    "version_line": "cmake version 3.28.3"
  },
  "_summary": {
    "total_tools": 20,
    "found": 18,
    "missing": 2,
    "missing_core": [],
    "missing_recommended": [
      "cvise",
      "creduce"
    ]
  }
}
```

#### `llmtk context export --deep`

For a detailed understanding of the project structure, an agent can request a deep context export.

**Command**:
```bash
llmtk context export --deep
```

**Output (`exports/context.json`)**:
```json
{
  "deep_export": true,
  "compile_commands": "exports/compile_commands.json",
  "cmake_file_api": {
    "dir": "exports/cmake-file-api/",
    "files": [
      "cache-v2-...",
      "codemodel-v2-...",
      "toolchains-v1-..."
    ]
  },
  "generated_at": "...",
  "deep_info": {
    "codemodel": {
      "configurations": [
        "Debug"
      ],
      "targets": [
        "my-awesome-project"
      ]
    },
    "cache": {
      "CMAKE_CXX_COMPILER": "/usr/bin/g++",
      "CMAKE_CXX_STANDARD": "23"
    },
    "toolchains": {
      "cxx": {
        "compiler": {
          "id": "GNU",
          "version": "13.2.0"
        }
      }
    }
  }
}
```
