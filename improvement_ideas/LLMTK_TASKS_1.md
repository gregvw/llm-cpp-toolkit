# High-impact additions

1. Add first-class SARIF everywhere
   Right now we already standardize JSON for agents. Add a unified `llmtk analyze --sarif` that either (a) requests native SARIF when available or (b) converts tool output to SARIF. Why: SARIF is the lingua franca for static analysis and lets agents merge results from gcc/clang/clang-tidy/cppcheck/iwyu into one file with de-duped rules/locations.

* GCC: has SARIF output (and multiple formats in GCC 15). ([GCC][2])
* Clang has SARIF machinery (and tools like clang-tidy → SARIF converters exist). ([Clang][3])
* WG21 P3358 makes the case for ecosystem-wide SARIF. ([WG21][4])
  Concretely:

```bash
llmtk analyze --sarif exports/reports/combined.sarif \
  --from clang-tidy,cppcheck,iwyu,gcc,clang
```

…and ship a tiny adapter that uses native flags when present, else runs through converters (e.g., `clang-tidy-sarif`), then merges.

2. CMake File-API + Presets “deep export”
   We already export compile\_commands and file-api replies; add a single `llmtk context export --deep` that:

* forces a configure run with `cmake_file_api(QUERY ...)` for CODEMODEL/CACHE/CMAKEFILES/TOOLCHAINS,
* captures the *exact* preset used (configure/build/test) and emits a compact agent-ready `context.json` that maps targets↔sources↔include-dirs↔toolchains. ([CMake][5])
  Also validate/emit the active `CMakePresets.json` schema version (agents often need to know if `inherits`/`condition` are available). ([CMake][6])

3. Repro reducer as a first-class command
   We mention reduction with cvise; make `llmtk reduce` bulletproof: detect/guide the user to cvise or creduce, run under a timeout, auto-minimize via `clang_delta` passes, and attach a SARIF (or text) “why this repro fails” post-mortem. Include a research-backed default pass order. ([GitHub][7])

# Quality & ergonomics

4. “LLM-safe stderr” thinning
   Ship `llmtk stderr-thin` that canonicalizes compiler/Linker diagnostics for context conservation:

* collapse duplicate template instantiation chains,
* keep first + last instantiation frames,
* keep the rule ID and `-W...`/`-Werror` switch (so the agent can suggest the fix),
* output either SARIF or a compact JSON with fields: `rule`, `primaryLocation`, `trace[]`, `fixit?`.
  GCC/Clang both expose diagnostic options; standardizing them makes our agents better at remediation. ([Clang][8])

5. “Capabilities for Agents” is great—version it
   We already generate `exports/capabilities.json`. Add semver + a `$schema` URL so agents can validate and branch behavior cleanly; include per-tool fields: `version`, `invocation`, `supports.sarif`, `supports.json`, `maxOutputBytes`, `typicalLatencyMs`. (Our README calls this out implicitly—make it formal.) ([GitHub][1])

6. Opinionated presets, but toggleable
   Our init presets with sanitizer variants are excellent; add:

* `--preset=oss-hardening` (Werror, -fno-omit-frame-pointer, FORTIFY, LTO opt-in),
* `--preset=fast-iter` (ccache/sccache + mold/lld + -Og + asan/ubsan off),
* `--preset=tsan-ci` (TSan + deterministic seeds).
  Document them via the Presets manual so users understand inheritance/conditions. ([CMake][6])

7. Supply chain ready-made
   We already have multiple packaging paths (Homebrew/Snap/Flatpak/AppImage/Nix/npm). Add:

* Python “single-file” install via `pipx` for folks who can’t use curl|bash,
* reproducible container (GHCR) *and* a devcontainer.json for instant try-out,
* signed release artifacts + checksums in **Releases**. (Our repo shows packaging scaffolding; publishing releases will make adoption easier.) ([GitHub][1])

# Agent-specific wins

8. One-shot “LLM context pack”
   `llmtk context pack --redact` → produces a tarball with: *thin* diagnostics, compile\_commands, file-api replies, top-N headers by include weight, and a redaction manifest (paths/emails/tokens stripped). Agents love a single archive to ingest. (Build on our `exports/` design.) ([GitHub][1])

9. MCP/Tools registry bridge
   Expose llmtk commands as a simple MCP server (or publish a tiny MCP tool that shells out to llmtk). That removes per-model glue (the “N×M tools” headache). Use our capabilities file to advertise callable actions (`doctor`, `context export`, `analyze`, `reduce`). ([GitHub][1])

10. “Fixit loop”
    Add `llmtk tidy --apply` and `llmtk format --check|--apply` so an agent can propose and *apply* safe clang-tidy fixes, then re-run `analyze --sarif` to see if issues declined.

# Nice-to-have utilities

* **Build/Perf probes**: `llmtk bench` wrapping `hyperfine` for *configure*, *build*, *test* timing; collect ccache stats; surface hot targets to agents. ([GitHub][1])
* **Deps and graph**: export target graph (from File-API CODEMODEL) to JSON and, optionally, Graphviz for humans. ([CMake][9])
* **Package managers**: detect and emit vcpkg/conan lock info into context so agents know where libs come from and how to install them.
* **CTest integration**: `llmtk test --json` (parse CTest XML) → stable JSON/SARIF test results.
* **Security/quality gate**: `llmtk gate` fails CI if SARIF severity crosses a threshold, with a concise summary (count by rule/severity).

# Docs & onboarding (tiny edits, huge payoff)

* Our README already reads like a product page (nice). Consider adding a 90-second “new user path”:

  ```bash
  curl -sSL ... | bash
  llmtk doctor
  llmtk init --existing .
  llmtk context export --deep
  llmtk analyze --sarif
  llmtk pack --redact out.llmctx.tgz
  ```

  and link to **Quickstart**, **Tool Reference**, **Distribution** (those pages exist in the repo nav). ([GitHub][1])
* Add a short “For Agents” page (or expand `AGENTS.md`) with contract examples: *input → llmtk command → expected artifacts → what to read next*. (I see AGENTS.md present; just flesh it out with real transcripts.) ([GitHub][1])

# 3 tangible PR-sized tasks (We could merge this week)

1. **Universal SARIF merger**

* New module `modules/sarif_merge.py` + `llmtk analyze --sarif` flag.
* Use native SARIF where possible; else convert via `clang-tidy-sarif`, then merge. ([Crates.io][10])

2. **stderr thinner**

* `modules/thin_diagnostics.py` that parses GCC/Clang output, collapses template chains, emits compact JSON (and optionally SARIF).

3. **Deep context exporter**

* Ensure a configure with file-api queries every time; write `exports/context.json` with targets, compdb path, preset used, toolchain triplet, linkers, standard, and cache entries most agents need. ([CMake][9])

[1]: https://github.com/gregvw/llm-cpp-toolkit "GitHub - gregvw/llm-cpp-toolkit: A common collection of CLI tools to assist your AI coding agents with your C++ development tasks."
[2]: https://gcc.gnu.org/wiki/SARIF?utm_source=chatgpt.com "SARIF - GCC Wiki"
[3]: https://clang.llvm.org/doxygen/classclang_1_1SarifDocumentWriter.html?utm_source=chatgpt.com "clang::SarifDocumentWriter Class Reference"
[4]: https://wg21.link/P3358R0?utm_source=chatgpt.com "P3358R0: SARIF for Structured Diagnostics - WG21 Links"
[5]: https://cmake.org/cmake/help/latest/command/cmake_file_api.html?utm_source=chatgpt.com "cmake_file_api — CMake 4.1.1 Documentation"
[6]: https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html?utm_source=chatgpt.com "cmake-presets(7) — CMake 4.1.1 Documentation"
[7]: https://github.com/marxin/cvise?utm_source=chatgpt.com "marxin/cvise: Super-parallel Python port of the C-Reduce"
[8]: https://clang.llvm.org/docs/DiagnosticsReference.html?utm_source=chatgpt.com "Diagnostic flags in Clang — Clang 22.0.0git documentation"
[9]: https://cmake.org/cmake/help/latest/manual/cmake-file-api.7.html?utm_source=chatgpt.com "cmake-file-api(7) — CMake 4.1.1 Documentation"
[10]: https://crates.io/crates/clang-tidy-sarif?utm_source=chatgpt.com "clang-tidy-sarif - crates.io: Rust Package Registry"

