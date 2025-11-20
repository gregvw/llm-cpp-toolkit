# LLM C++ Toolkit - Master Roadmap

> **Last Updated**: 2025-11-20
> **Status**: Consolidated from existing task lists + external analysis

This document combines all improvement ideas from LLMTK_TASKS_1-4.md, EXTENSIONS.md, and external recommendations into a single prioritized roadmap organized by strategic value and implementation effort.

---

## 🎯 Strategic Framework

### North Star Goal
**Make C++ development with AI agents 10x more effective than generic coding assistants**

### Success Metrics (6-month validation)
1. ✅ 3-5 AI agent researchers say "llmtk is essential for C++ experiments"
2. ✅ 2+ published case studies showing dramatic before/after improvements
3. ✅ Integration PR merged into Cursor, Continue, or Aider
4. ✅ 50+ GitHub stars, 5+ external contributors
5. ✅ 1000+ pipx/brew installs tracked

### Validation Gates
- **Phase 1 (Months 1-2)**: Core agent UX - proves unique value
- **Phase 2 (Months 3-4)**: Community adoption - proves market fit
- **Phase 3 (Months 5-6)**: Ecosystem integration - proves staying power

---

## 📊 Prioritization Matrix

Tasks rated on:
- **Impact**: 🔥🔥🔥 (Critical) → 🔥 (Nice-to-have)
- **Effort**: S (Small, <1 day) | M (Medium, 2-5 days) | L (Large, 1-2 weeks) | XL (Multi-week)
- **Dependency**: What must be done first
- **Phase**: When to tackle (1, 2, or 3)

---

## 🚀 PHASE 1: Core Agent UX (Months 1-2)
*Goal: Prove unique value to early adopters*

### Tier 1A: Quick Wins (Ship This Week)

#### T1A.1 - Universal SARIF Merger 🔥🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: None

**What**: Single `llmtk analyze --sarif` that merges clang-tidy, IWYU, cppcheck, gcc, clang outputs
- Native SARIF where available (GCC 15, Clang)
- Converter fallback (clang-tidy-sarif, custom adapters)
- De-duplicated rules, unified severity mapping
- Output: `exports/reports/analysis.sarif`

**Why**: SARIF is lingua franca for static analysis. Agents get one file instead of parsing 5 tool formats.

**Status**: Framework exists (`modules/sarif_converter.py`, `modules/sarif_merge.py`), needs completion

**References**: LLMTK_TASKS_1.md #1, WG21 P3358

---

#### T1A.2 - LLM-Safe stderr Thinning 🔥🔥🔥
**Effort**: S | **Phase**: 1 | **Deps**: None

**What**: `llmtk stderr-thin` canonicalizes compiler/linker diagnostics for context conservation
- Collapse duplicate template instantiation chains (keep first + last frames)
- Extract rule ID, `-W...` flags, fixit suggestions
- Budget-aware output (configurable token limits)
- Output: JSON with `{rule, primaryLocation, trace[], fixit?}` + optional SARIF

**Why**: Template errors are 500+ lines of noise. Agents waste context on duplicates. This makes C++ errors digestible.

**Status**: Partially implemented (`llmtk/commands/stderr_thin.py`, `modules/stderr_thin.py`)

**Enhancement**: Add tiered modes (summary/focused/detailed) with token budgets

**References**: LLMTK_TASKS_1.md #4, My recommendation #13 (budget-aware context)

---

#### T1A.3 - Deep Context Exporter 🔥🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: None

**What**: `llmtk context export --deep` forces CMake configure with File API query
- Exports: CODEMODEL, CACHE, CMAKEFILES, TOOLCHAINS
- Captures active CMakePresets.json (detect version, inherits, conditions)
- Validates and normalizes to `exports/context.json`:
  ```json
  {
    "targets": {...},
    "compdb_path": "exports/compile_commands.json",
    "preset_used": "release-asan",
    "toolchain": {...},
    "cache_entries": {...},
    "schema_version": "1.0.0"
  }
  ```

**Why**: Agents need structured project understanding. This is the foundation for all analysis.

**Status**: Partial implementation exists (`llmtk/commands/context.py`)

**Enhancement**: Add `--token-budget` to prune low-value files (vendored deps, generated code)

**References**: LLMTK_TASKS_1.md #2, LLMTK_TASKS_3.md #1, My recommendation #13

---

#### T1A.4 - Capabilities Versioning & Schema 🔥🔥
**Effort**: S | **Phase**: 1 | **Deps**: None

**What**: Formalize `exports/capabilities.json` with semver + `$schema`
- Add per-tool metadata: `version`, `invocation`, `supports.{sarif,json}`, `maxOutputBytes`, `typicalLatencyMs`
- Publish schema URL for validation
- Enable agents to detect toolkit version and adapt behavior

**Why**: Agents can branch behavior cleanly. Future-proof for breaking changes.

**Status**: Basic version exists (`llmtk/commands/capabilities.py`)

**Enhancement**: Auto-generate from `manifest/tools.yaml` + `manifest/commands.yaml`

**References**: LLMTK_TASKS_1.md #5

---

### Tier 1B: Differentiated Features (Week 2-3)

#### T1B.1 - Smart Diagnostic Explanations 🔥🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: T1A.1 (SARIF merger)

**What**: Enrich SARIF/JSON diagnostics with contextual "why" and "how to fix"
- Link to C++ Core Guidelines (already have `core_guidelines/*.json`!)
- Add common fix patterns for each diagnostic
- Impact assessment (correctness vs. performance vs. style)
- Before/after code examples
- Output format:
  ```json
  {
    "diagnostic": "modernize-use-auto",
    "guideline": {
      "id": "ES.11",
      "title": "Use auto to avoid redundant repetition",
      "url": "https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#Res-auto"
    },
    "why": "Improves maintainability when type changes",
    "fix_pattern": "Replace explicit type with auto when initializer determines type",
    "example": {
      "before": "std::vector<int>::iterator it = vec.begin();",
      "after": "auto it = vec.begin();"
    },
    "impact": "style",
    "confidence": 0.95
  }
  ```

**Why**: This is UNIQUE VALUE. Agents learn *context*, not just patterns. Reduces back-and-forth.

**Implementation**:
1. Create `knowledge_base/diagnostics.yaml` mapping rule IDs → explanations
2. Build index from `core_guidelines/*.json`
3. Integrate into SARIF output as `rule.helpUri` and `result.message`
4. Start with top 20 clang-tidy checks, expand iteratively

**Status**: Foundation exists (Core Guidelines JSON), needs integration

**References**: My recommendation #2

---

#### T1B.2 - Interactive Fix Application 🔥🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: T1A.1 (SARIF), T1B.1 (explanations)

**What**: `llmtk fix` wraps clang-tidy/clang-format with safety and preview
- `llmtk fix --preview --format=diff` - Show all changes as unified diff
- `llmtk fix --interactive` - Agent reviews each fix before applying
- `llmtk fix --categories=modernization,performance --confidence=high`
- `llmtk fix --rollback` - Undo last fix batch (git stash under the hood)
- Outputs: `exports/fixes/applied.json` with before/after, success rate

**Why**: Makes fix application safe and incremental. Builds user trust. Agents can iterate confidently.

**Implementation**:
1. Add `llmtk/commands/fix.py`
2. Use `clang-tidy --fix --format-style=file` with filtering
3. Track changes with git stash or temporary commits
4. Emit structured report of applied fixes

**Status**: Not implemented (manifest defines `llmtk tidy --apply` and `llmtk format`)

**References**: LLMTK_TASKS_1.md #10, My recommendation #3

---

#### T1B.3 - One-Shot Context Pack 🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: T1A.2 (stderr-thin), T1A.3 (deep context)

**What**: `llmtk context pack --redact` → single tarball for agent ingestion
- Includes: thin diagnostics, compile_commands, file-api replies, top-N headers by include weight
- Redaction manifest: strips paths, emails, tokens, API keys
- Outputs: `exports/llmctx-{timestamp}.tar.gz` + `manifest.json`

**Why**: Agents love a single artifact to download and ingest. Simplifies sharing with team/remote agents.

**Implementation**:
1. Add `llmtk/commands/pack.py`
2. Archive `exports/` contents with optional redaction pass
3. Generate `manifest.json` with file inventory, checksums, schema version
4. Optional encryption for sensitive codebases

**Status**: Not implemented

**References**: LLMTK_TASKS_1.md #8, My recommendation #13

---

#### T1B.4 - Differential Analysis (Before/After) 🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: T1A.1 (SARIF merger)

**What**: `llmtk diff-analyze --base=main --head=feature` shows impact of changes
- Compare warnings (added, fixed, net improvement)
- Compare compilation time (ccache stats, parallelism)
- Compare binary size, test coverage (if available)
- Output: `exports/diff-analysis.json`
  ```json
  {
    "warnings": {"added": 2, "fixed": 15, "net_improvement": 13},
    "compilation_time": {"before": "45.2s", "after": "38.1s", "improvement": "15.7%"},
    "binary_size": {"before": "2.4 MB", "after": "2.1 MB"},
    "tests": {"before": {"pass": 42, "fail": 1}, "after": {"pass": 43, "fail": 0}}
  }
  ```

**Why**: Agents can objectively measure if their changes improved the codebase. Great for PR descriptions.

**Implementation**:
1. Add `llmtk/commands/diff_analyze.py`
2. Run analysis on both commits, compute deltas
3. Leverage existing `modules/diff_context.py`

**Status**: Framework exists (`modules/diff_context.py`), needs command wrapper

**References**: My recommendation #6

---

### Tier 1C: Distribution & Onboarding

#### T1C.1 - Supply Chain Hardening 🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: None

**What**: Production-ready packaging and distribution
- Add pipx installer with SHA256 verification (single-file Python install)
- Publish signed GitHub releases with checksums
- Reproducible container (GHCR) + devcontainer.json for instant try-out
- Update installers: Homebrew formula, Snap, Flatpak, AppImage

**Why**: Lowers adoption barrier. Builds trust with security-conscious teams.

**Status**: Scaffolding exists (`installers/`, `containers/`), needs release automation

**References**: LLMTK_TASKS_1.md #7

---

#### T1C.2 - 90-Second Quickstart Path 🔥🔥
**Effort**: S | **Phase**: 1 | **Deps**: T1C.1

**What**: Streamlined new user experience
```bash
curl -sSL https://llmtk.dev/install.sh | bash
llmtk doctor
llmtk init --existing .
llmtk context export --deep
llmtk analyze --sarif
llmtk pack --redact out.llmctx.tar.gz
```

**Why**: First impression matters. Show value in 90 seconds.

**Implementation**:
- Create `docs/QUICKSTART.md` (exists, needs update)
- Add `scripts/demo.sh` that runs the above on sample project
- Record 30-second video walkthrough for README

**Status**: Docs exist, need refinement

**References**: LLMTK_TASKS_1.md, My recommendation #18

---

#### T1C.3 - MCP Server Integration 🔥🔥
**Effort**: M | **Phase**: 1 | **Deps**: T1A.4 (capabilities)

**What**: First-class Model Context Protocol support
- Stabilize `llmtk agent mcp` stdio server
- Expose operations: `read_file`, `write_file`, `list_directory`, `list_exports`, `get_capabilities`, `expand_context`
- Publish adapters for Cursor, Continue, Aider (exist in `integrations/`)
- Add timeout management, error handling, streaming for large files

**Why**: MCP is the emerging standard for agent-IDE integration. First-mover advantage.

**Status**: Implemented (`llmtk/commands/agent.py`), needs docs and testing

**References**: LLMTK_TASKS_1.md #9

---

### Tier 1D: Documentation (Critical for Adoption)

#### T1D.1 - "For Agents" Guide 🔥🔥
**Effort**: S | **Phase**: 1 | **Deps**: T1A-T1C complete

**What**: Expand `docs/AGENTS.md` with real-world examples
- Input → llmtk command → expected artifacts → what to read next
- Example transcripts: "How Claude fixed a memory leak using llmtk"
- Contract definitions for each command (input schema, output schema, error codes)

**Why**: Agents and agent developers need clear contracts to build integrations.

**Status**: Partial (`docs/TUTORIAL.md` exists)

**References**: LLMTK_TASKS_1.md, My recommendation #18

---

#### T1D.2 - Benchmark Showcase 🔥
**Effort**: S | **Phase**: 1 | **Deps**: T1B.4 (differential analysis)

**What**: Publish comparative benchmarks
- Context size reduction: before/after llmtk (target: 10x compression)
- Time to first insight: manual (30min) vs. llmtk (30s)
- Analysis coverage: generic tools vs. llmtk (demonstrate C++-specific value)

**Why**: Data-driven proof of value. Marketing material for adoption.

**Status**: Not started

**References**: LLMTK_TASKS_2.md, My recommendation #28

---

## 🌱 PHASE 2: Community Adoption (Months 3-4)
*Goal: Prove market fit, enable contributions*

### Tier 2A: Advanced Agent Features

#### T2A.1 - Repro Reducer (First-Class) 🔥🔥🔥
**Effort**: L | **Phase**: 2 | **Deps**: T1A.1 (SARIF)

**What**: `llmtk reduce` bulletproofs test case minimization
- Auto-detect cvise/creduce availability
- Run under timeout with progress tracking
- Use research-backed pass order (clang_delta, topformflat, etc.)
- Attach SARIF/JSON "why this repro fails" post-mortem
- Output: `exports/repros/minimized.cpp` + `report.json`

**Why**: Agents can create minimal reproducers for bug reports. Critical for AI-generated code debugging.

**Status**: Framework exists (`modules/reduce.sh`), needs command wrapper

**References**: LLMTK_TASKS_1.md #3, My recommendation #8

---

#### T2A.2 - Performance Hotspot Identification 🔥🔥
**Effort**: L | **Phase**: 2 | **Deps**: None

**What**: `llmtk profile --workload=./benchmark --top=10` integrates profilers
- Support: perf (Linux), Instruments (macOS), VTune (Intel)
- Extract compiler optimization remarks (`-Rpass`)
- Output: `exports/perf/hotspots.json` with function rankings, call graphs
- `llmtk profile suggest` → AI-driven optimization hints based on data

**Why**: Agents can suggest optimizations backed by profiling data, not guesses.

**Status**: Not implemented

**References**: My recommendation #8

---

#### T2A.3 - Dependency Vulnerability Scanning 🔥🔥
**Effort**: M | **Phase**: 2 | **Deps**: None

**What**: `llmtk deps audit --source=conan,vcpkg,cmake-fetch`
- Integrate GitHub Advisory Database, CVE feeds
- License compliance checking
- Suggest updates for vulnerable dependencies
- Output: `exports/deps/audit.json` + SARIF

**Why**: Security is table stakes. Differentiates from generic tools.

**Status**: Not implemented (partial deps graph exists in `modules/dependency_graph.py`)

**References**: My recommendation #7

---

#### T2A.4 - Code Smell & Anti-Pattern Detection 🔥🔥
**Effort**: L | **Phase**: 2 | **Deps**: T1A.1 (SARIF)

**What**: `llmtk patterns detect --categories=ownership,resource-mgmt,concurrency`
- Detect: god classes (>1000 LOC), circular dependencies, missing RAII, unsafe concurrency
- Use tree-sitter for AST-based analysis
- Output: `exports/patterns/smells.sarif` with refactoring suggestions

**Why**: Guides architectural refactoring conversations. Prevents technical debt.

**Status**: Not implemented

**References**: My recommendation #5, LLMTK_TASKS_3.md #1 (semantic understanding)

---

#### T2A.5 - Build Performance Metrics 🔥🔥
**Effort**: M | **Phase**: 2 | **Deps**: None

**What**: `llmtk bench --runs=3 --warmup=1` benchmarks configure/build/test
- Capture: duration per stage, peak memory, parallelism analysis, slow TUs
- Collect ccache/sccache hit rates
- Output: `exports/perf/bench.json` with time-series data

**Why**: Agents can identify build bottlenecks and suggest improvements.

**Status**: Framework exists (`llmtk/commands/bench.py` stub, manifest defines it)

**References**: LLMTK_TASKS_1.md, My recommendation #1

---

### Tier 2B: Ecosystem Integration

#### T2B.1 - Plugin/Extension System 🔥🔥🔥
**Effort**: L | **Phase**: 2 | **Deps**: T1A.4 (capabilities)

**What**: Enable custom analyzers and integrations
```bash
llmtk plugin add custom-analyzer --command="./my_analyzer --json"
llmtk plugin list  # Shows built-in + custom
```

Plugin manifest:
```yaml
name: custom-analyzer
version: 1.0.0
outputs:
  - format: json
    schema: sarif-2.1.0
integration:
  stage: analyze  # Runs during `llmtk analyze`
```

**Why**: Community can extend without forking. Enables domain-specific tooling (embedded, gamedev, HPC).

**Status**: Not implemented

**References**: My recommendation #10, LLMTK_TASKS_2.md

---

#### T2B.2 - Watch Mode for Continuous Feedback 🔥
**Effort**: S | **Phase**: 2 | **Deps**: None

**What**: `llmtk watch --on-change="analyze src/" --debounce=1s`
- Monitor file changes, trigger commands automatically
- Integrate with entr/watchexec
- Stream results to MCP clients

**Why**: Agents get instant feedback during iterative development.

**Status**: Not implemented

**References**: My recommendation #11

---

#### T2B.3 - Preset Configurations for Domains 🔥🔥
**Effort**: M | **Phase**: 2 | **Deps**: None

**What**: `llmtk init --preset={gamedev,embedded,scientific,web,ml}`
- GameDev: profiling, asset pipelines, hot reload, Tracy integration
- Embedded: cross-compilation, size optimization, static analysis, MISRA checks
- Scientific: Fortran interop, BLAS/LAPACK, parallel builds, HPC toolchains
- Web: WebAssembly, Emscripten presets
- ML: CUDA/ROCm, PyTorch/TensorFlow C++ API

**Why**: Instant setup for common use cases. Shows domain expertise.

**Status**: Partial (templates exist in `templates/`, needs expansion)

**References**: My recommendation #12, LLMTK_TASKS_3.md #5, LLMTK_TASKS_4.md, EXTENSIONS.md

---

#### T2B.4 - CI Templates Generator 🔥🔥
**Effort**: M | **Phase**: 2 | **Deps**: T1A.1 (SARIF)

**What**: `llmtk ci generate --platform=github-actions,gitlab-ci --coverage --sanitizers`
- One-command CI/CD setup
- Matrix builds (compilers, C++ standards, platforms)
- Coverage upload (Codecov, Coveralls)
- SARIF upload to GitHub Code Scanning

**Why**: Lowers barrier to best practices. Great demo material.

**Status**: Not implemented

**References**: My recommendation #14

---

### Tier 2C: Learning & Feedback

#### T2C.1 - Agent Learning Loop (Success Tracking) 🔥🔥
**Effort**: L | **Phase**: 2 | **Deps**: T1B.2 (fix application)

**What**: Track which agent actions succeed
```yaml
agent_feedback:
  pattern_id: "undefined_reference"
  fix_success_rate: 0.87
  average_attempts: 2.3
  common_fixes:
    - "Add missing #include"
    - "Link library in CMakeLists.txt"
```

- Local feedback database (SQLite)
- Opt-in telemetry for cross-project learning
- `llmtk feedback export` for sharing anonymized data

**Why**: Agents learn from experience. Community can crowdsource fix patterns.

**Status**: Not implemented

**References**: LLMTK_TASKS_2.md #1, LLMTK_TASKS_3.md #4, My recommendation #1

---

#### T2C.2 - Recipe Library 🔥
**Effort**: M | **Phase**: 2 | **Deps**: None

**What**: Crowdsourced solutions to common problems
```bash
llmtk recipe search "fix undefined behavior"
llmtk recipe apply asan-ubsan-setup
```

- Store in `cookbook/recipes/*.yaml`
- Community contributions via PR
- Versioned, tested recipes

**Why**: Lowers learning curve. Builds community.

**Status**: Partial (`docs/COOKBOOK.md` exists)

**References**: My recommendation #17

---

### Tier 2D: Documentation & Community

#### T2D.1 - Interactive Tutorial Mode 🔥
**Effort**: M | **Phase**: 2 | **Deps**: T1C.2 (quickstart)

**What**: `llmtk tutorial start` - guided walkthrough with verification
- Hands-on exercises: init project, run analysis, apply fixes, export context
- Built-in validation (checks that user completed steps correctly)
- Progress tracking

**Why**: Teaches agents and developers how to use toolkit effectively.

**Status**: Not implemented

**References**: My recommendation #16

---

#### T2D.2 - Agent Success Stories / Case Studies 🔥🔥
**Effort**: M | **Phase**: 2 | **Deps**: Real usage from Phase 1

**What**: `examples/agent-conversations/` directory with real transcripts
- "How Claude fixed a memory leak using llmtk"
- "Optimizing build time from 5min to 30s"
- "Migrating from C++11 to C++20"
- Before/after metrics, full command logs

**Why**: Social proof. Shows concrete value. Marketing material.

**Status**: Not started

**References**: My recommendation #18

---

## 🚀 PHASE 3: Ecosystem Leadership (Months 5-6)
*Goal: Become the standard for AI + C++*

### Tier 3A: Advanced Analysis

#### T3A.1 - Semantic Diff Analysis (AST-Aware) 🔥🔥
**Effort**: XL | **Phase**: 3 | **Deps**: T2A.4 (patterns)

**What**: Beyond text diffs to structural understanding
- Use tree-sitter or clang LibTooling for AST diffing
- Identify semantic changes (not just whitespace/formatting)
- Impact analysis: which functions/classes affected, test surface needed
- Output: `exports/diff/semantic.json`

**Why**: Agents can understand *what* changed, not just *where*. Smarter PR reviews.

**Status**: Not implemented

**References**: LLMTK_TASKS_2.md #5, LLMTK_TASKS_3.md #1

---

#### T3A.2 - Cross-Platform Build Matrix Testing 🔥🔥
**Effort**: XL | **Phase**: 3 | **Deps**: T2B.3 (presets)

**What**: `llmtk matrix define --compilers=gcc-13,clang-18,msvc --std=c++20,c++23`
- Run all combinations in containers/Nix
- Parallel execution
- Identify portability issues
- Output: `exports/matrix/results.sarif`

**Why**: Catches portability issues before CI. Agents can test fixes across compilers locally.

**Status**: Not implemented

**References**: My recommendation #4

---

#### T3A.3 - Fuzzer Integration 🔥
**Effort**: L | **Phase**: 3 | **Deps**: T2A.1 (repro reducer)

**What**: `llmtk fuzz --engine=libfuzzer,afl++ --corpus=./corpus`
- Export minimized crashes and sanitizer traces
- JSON/SARIF output for agent consumption
- Auto-minimize crash reproducers

**Why**: Security-critical projects need fuzzing. Agents can triage crash reports.

**Status**: Not implemented

**References**: LLMTK_TASKS_4.md

---

#### T3A.4 - Symbol-Level Dependency Analysis 🔥
**Effort**: L | **Phase**: 3 | **Deps**: T2A.4 (patterns)

**What**: Beyond target dependencies to symbol imports/exports
- Track which symbols are used from each library
- Identify unused dependencies (link-time analysis)
- Suggest minimal link surface
- Output: `exports/deps/symbols.json` + Graphviz

**Why**: Reduces binary size, speeds up linking. Agents can suggest dependency cleanup.

**Status**: Partial (`modules/dependency_graph.py` for targets)

**References**: LLMTK_TASKS_1.md, LLMTK_TASKS_3.md #2

---

### Tier 3B: Advanced Integrations

#### T3B.1 - LLM Provider Adapters 🔥
**Effort**: M | **Phase**: 3 | **Deps**: T1A.3 (context export)

**What**: Model-specific context optimization
```bash
llmtk export --format=claude  # Optimized for Claude's 200k context
llmtk export --format=gpt4    # Optimized for GPT-4's structure
llmtk export --format=gemini  # Optimized for Gemini's long context
```

- Different chunking strategies per model
- Token counting per provider
- Format preferences (XML vs JSON vs Markdown)

**Why**: Maximizes effectiveness per LLM. Differentiates from generic tools.

**Status**: Not implemented

**References**: LLMTK_TASKS_2.md #4

---

#### T3B.2 - AI Training Data Generation 🔥
**Effort**: L | **Phase**: 3 | **Deps**: T3A.1 (semantic diff)

**What**: Export project in formats suitable for fine-tuning
- Before/after examples from git history
- Synthetic test cases from existing code
- SARIF + fix pairs for supervised learning

**Why**: Enables researchers to train C++-specific models. Unique value proposition.

**Status**: Not implemented

**References**: LLMTK_TASKS_3.md #3

---

#### T3B.3 - Interactive Debugging Support 🔥
**Effort**: L | **Phase**: 3 | **Deps**: T2A.2 (profiling)

**What**: `llmtk debug --auto` generates GDB/LLDB scripts
- Breakpoint suggestions based on error locations
- Stack trace simplification for agent consumption
- Watchpoint generation for data races

**Why**: Closes the loop from analysis → debugging. Agents can drive debugging sessions.

**Status**: Not implemented

**References**: LLMTK_TASKS_3.md #4

---

### Tier 3C: Ecosystem Polish

#### T3C.1 - Session Memory & Context Replay 🔥🔥
**Effort**: L | **Phase**: 3 | **Deps**: T2C.1 (learning loop)

**What**: Persistent agent conversation state
```bash
llmtk session start --id=fix-memory-leak
llmtk analyze --session=fix-memory-leak  # Results cached with context
llmtk session recall --query="previous memory issues"
llmtk session export --id=fix-memory-leak  # Share with team
```

**Why**: Agents build on previous work instead of starting from scratch. Massive efficiency gain.

**Status**: Not implemented

**References**: My recommendation #1

---

#### T3C.2 - Parallel Build Intelligence 🔥
**Effort**: M | **Phase**: 3 | **Deps**: T2A.5 (bench)

**What**: Detect and report build bottlenecks
- Identify circular dependencies slowing parallelism
- Suggest `-j` optimization based on machine cores
- Analyze critical path in build graph

**Why**: Speeds up development iteration. Agents can suggest build improvements.

**Status**: Not implemented

**References**: LLMTK_TASKS_2.md #2

---

#### T3C.3 - Enhanced Reproducibility Capture 🔥
**Effort**: M | **Phase**: 3 | **Deps**: T1C.1 (supply chain)

**What**: Snapshot environment for deterministic rebuilds
- Capture: env vars, toolchain digests, build inputs, package versions
- Export: `exports/repro/environment.json`
- `llmtk repro apply` restores environment

**Why**: Critical for debugging non-deterministic issues. Research-grade reproducibility.

**Status**: Not implemented

**References**: LLMTK_TASKS_4.md

---

---

## 📦 OPTIONAL EXTENSIONS (Community-Driven)

These are valuable but lower priority. Can be tackled by contributors or as Phase 4.

### Modern C++ Libraries Integration

From EXTENSIONS.md, these could be opt-in plugins:

- **Testing**: Catch2, doctest, GoogleTest, ApprovalTests, rapidcheck
- **Benchmarking**: Google Benchmark
- **Formatting/Logging**: {fmt}, spdlog
- **JSON/Config**: nlohmann/json, toml++, simdjson
- **Concurrency**: Cpp-Taskflow, moodycamel::ConcurrentQueue
- **Reflection**: magic_enum, nameof
- **Package Management**: CPM (CMake Package Manager)
- **Scaffolding**: ModernCppStarter, Pitchfork conventions
- **UI Polish**: rich, textual, indicators (Python progress bars/tables)
- **CLI Parsing**: cxxopts (for scaffolded projects)

**Implementation Strategy**: Plugin system (T2B.1) + community recipes

---

## 🎯 PRIORITY RANKING (If resources are limited)

### Must-Have (Validates core thesis)
1. T1A.1 - SARIF Merger
2. T1A.2 - stderr Thinning
3. T1A.3 - Deep Context Export
4. T1B.1 - Smart Diagnostic Explanations ⭐ **UNIQUE VALUE**
5. T1B.2 - Interactive Fix Application
6. T1C.1 - Supply Chain Hardening
7. T1C.3 - MCP Integration
8. T1D.1 - "For Agents" Guide

### Should-Have (Proves market fit)
9. T1B.3 - Context Pack
10. T1B.4 - Differential Analysis
11. T1C.2 - 90-Second Quickstart
12. T2A.1 - Repro Reducer
13. T2B.1 - Plugin System ⭐ **FUTURE-PROOF**
14. T2B.3 - Domain Presets
15. T2C.2 - Recipe Library
16. T2D.2 - Case Studies ⭐ **MARKETING**

### Nice-to-Have (Ecosystem leadership)
17. T2A.2 - Performance Profiling
18. T2A.3 - Dependency Auditing
19. T2A.5 - Build Benchmarking
20. T3A.1 - Semantic Diff Analysis
21. T3C.1 - Session Memory ⭐ **GAME-CHANGER**

---

## 🗓️ SUGGESTED SPRINT PLAN

### Sprint 1 (Week 1-2): Foundation
- T1A.1 - SARIF Merger
- T1A.2 - stderr Thinning enhancements
- T1A.3 - Deep Context Export
- T1A.4 - Capabilities versioning

**Deliverable**: Core analysis pipeline complete

---

### Sprint 2 (Week 3-4): Differentiation
- T1B.1 - Smart Diagnostic Explanations ⭐
- T1B.2 - Interactive Fix Application
- T1B.4 - Differential Analysis

**Deliverable**: Showcase unique value, record demo video

---

### Sprint 3 (Week 5-6): Distribution
- T1C.1 - Supply Chain Hardening
- T1C.2 - 90-Second Quickstart
- T1C.3 - MCP Integration polish
- T1D.1 - "For Agents" Guide

**Deliverable**: v0.2.0 release, ready for early adopters

---

### Sprint 4 (Week 7-8): Community Prep
- T1B.3 - Context Pack
- T2C.2 - Recipe Library foundation
- T2D.2 - First case study (dogfood on real project)
- T1D.2 - Benchmark showcase

**Deliverable**: Marketing materials, outreach to AI agent researchers

---

### Sprint 5-6 (Month 3-4): Advanced Features
- T2A.1 - Repro Reducer
- T2B.1 - Plugin System
- T2B.3 - Domain Presets
- T2A.5 - Build Benchmarking

**Deliverable**: v0.3.0 release, community contributions enabled

---

### Sprint 7+ (Month 5-6): Leadership
- T3C.1 - Session Memory (if validated demand)
- T3A.2 - Cross-Platform Matrix (if portability is pain point)
- T2A.2 - Performance Profiling (if optimization is common request)
- T2A.3 - Dependency Auditing (if security is concern)

**Deliverable**: v1.0.0 release, ecosystem integrations

---

## 📈 Success Metrics (Revisited)

Track these metrics throughout phases:

### Usage Metrics
- Weekly active installs (pipx, brew, docker pulls)
- Commands most frequently run (via opt-in telemetry)
- Average context pack size reduction

### Community Metrics
- GitHub stars, forks, contributors
- Issues opened (signal of real usage)
- PRs from external contributors

### Integration Metrics
- Number of agent projects using llmtk
- Published case studies, blog posts
- Conference talks, paper citations

### Business Metrics (if applicable)
- Enterprise inquiries
- Support/consulting requests
- Sponsorships, grants

---

## 🤔 Open Questions for Validation

Before diving deep, gather feedback:

1. **Which diagnostic rules cause the most agent confusion?** (Informs T1B.1 priority)
2. **What's the typical context window constraint?** (Informs T1A.2, T1B.3 budgets)
3. **Do agents prefer SARIF or JSON?** (Informs T1A.1 defaults)
4. **What's the killer feature for early adopters?** (Informs sprint prioritization)
5. **Which domain preset is most requested?** (Informs T2B.3 order)

---

## 📝 Notes

- This roadmap is living document - update quarterly based on feedback
- Phases can overlap if resources allow parallel tracks
- Don't let perfect be enemy of good - ship early, iterate fast
- Community contributions can accelerate Tier 3 items

**Last Updated**: 2025-11-20
**Next Review**: 2025-12-20

---

## 🚀 Ready to Start?

Recommend starting with **Sprint 1** immediately. The foundation tasks are well-scoped, high-impact, and set up everything else.

**First PR**: T1A.1 (SARIF Merger) - it's ready to implement with existing infrastructure.

Let's build the bridge between AI and C++! 🌉
