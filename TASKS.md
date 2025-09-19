# LLM C++ Toolkit - Prioritized Tasks

## P0 - Unlock Agent Workflows
- [X] Universal SARIF analysis and fix-it loop: add `llmtk analyze --sarif` with native or converter pipelines for clang, clang-tidy, cppcheck, IWYU, gcc, and clang; ship `modules/sarif_merge.py` to dedupe results; pair it with `llmtk tidy --apply`, `llmtk format --check|--apply`, and a SARIF-aware `llmtk gate` so CI can enforce severity budgets.
- [X] Deep context export and packing: implement `llmtk context export --deep` to query the full CMake File API (codemodel, cache, toolchains), record preset metadata, toolchain triplets, linker and compiler standards, and per-translation-unit metrics (duration, memory, dependency count, template depth); add compile database enrichment and a redaction-aware `llmtk context pack --redact` tarball including top-N includes and thin diagnostics.
- [X] Hardened repro reducer: improve `llmtk reduce` to auto-detect or install cvise/creduce, apply research-backed pass orders, run with configurable timeouts and sanitizers, and emit SARIF or text post-mortems explaining the minimized failure.
- [X] Deterministic diagnostics and context budgets: provide `llmtk stderr-thin` (or integrate into build flows) that collapses template chains, highlights key warnings and errors, maps to structured LLVM diagnostics, and supports tiered context levels plus `--context-budget` and smart highlight filters for compilation commands.

## P1 - Platform Coverage and Tooling Depth
- [X] Capabilities schema and documentation refresh: version `exports/capabilities.json` with `$schema`, per-tool invocation metadata (JSON and SARIF support, output limits, latency), and extend docs with a 90-second new-user path in README, a cookbook with token budgets, context reduction benchmarks, and expanded `AGENTS.md` contract examples.
- [X] Preset and template expansion: add `--preset=oss-hardening`, `--preset=fast-iter`, `--preset=tsan-ci`, plus domain templates (`embedded`, `gamedev`, `scientific`, `systemsprog`) with documented inheritance and toggles for sanitizers, PIC, RTTI, exceptions, SIMD, and concurrency knobs.
- [X] Supply-chain ready distribution: publish a `pipx` installer, reproducible GHCR image and `devcontainer.json`, signed release artifacts with checksums, and ensure manifest pin alignment across Bash, Brew, and Nix installers.
- [X] Incremental and cached analysis: support `llmtk analyze --incremental` and `--cache-key` to reuse previous tool runs, share caches between clang-tidy, IWYU, and cppcheck, and expose cache management commands.
- [X] Structured testing exports: add `llmtk test --json` by parsing CTest XML, surface pass and fail reasons, integrate with SARIF gating, and allow dry previews of expensive test or context operations.
- [X] Error knowledge base: maintain a YAML library of diagnostic patterns with remediation guidance and required context tiers to help agents prioritize fixes.

## P2 - Agent Experience Enhancements
- [X] Agent feedback loop and adapters: design a JSON request channel (`expand_context`, etc.), expose llmtk via an MCP server and lightweight adapters for Cursor, Continue, and Aider, and ensure capability discovery comes from the manifest.
- [X] Initial implementation of a JSON-based request/response protocol and an `llmtk agent` command to handle `read_file`, `list_directory`, `write_file`, and `delete_file` requests.
- [ ] Build and performance insights: ship `llmtk bench` around hyperfine for configure, build, and test, report ccache stats, parallelism utilization, slowest translation units, and peak memory, and record these metrics in context exports.
- [ ] Dependency and symbol graph exports: derive target graphs from the CMake codemodel, emit JSON or Graphviz, include symbol-level dependency summaries around failures, and capture external package manager locks (vcpkg, conan) for agents.
- [ ] Incremental diff-oriented context: allow diff-based context packs, minimal dependency graphs per error, and an automated bisect helper that guides agents through regression hunts.
- [ ] LSP and structured diagnostics bridges: add `llmtk lsp-bridge` for clangd with diagnostic filtering, favor LLVM structured diagnostics over text parsing, and surface filtered results consistently with stderr thinning.
- [ ] Optional telemetry and dry-run controls: introduce opt-in, anonymized feature usage metrics, a global `--dry-run` preview mode for commands, and clear privacy documentation.

## P3 - Forward-Looking Exploration
- [ ] Fuzzer integration that exports minimized crashes and sanitizer traces in JSON or SARIF for agent consumption.
- [ ] WebAssembly and cross-compilation awareness, including Emscripten presets and multi-architecture toolchain exports.
- [ ] Enhanced reproducibility capture: snapshot environment variables, toolchain digests, and build inputs to enable deterministic rebuilds.
- [ ] Extended testing utilities: broaden security and quality gating (beyond SARIF severity) and integrate fuzz or test outputs into the context pack workflow.
