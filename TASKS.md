# Tasks

- [ ] Ship a merged SARIF pipeline (`llmtk analyze --sarif`) so every analyzer we already expose via JSON can emit the CI/IDE standard format in one artifact; this closes a visible gap in our current usage examples (`llmtk analyze src/ include/`) and aligns with the high-impact task list that highlights native/converted SARIF plus merging logic (`README.md:75`, `improvement_ideas/LLMTK_TASKS_1.md:3-17`).

- [ ] Extend llmtk context export with a true `--deep` mode that always drives the CMake File-API, records active presets, and condenses target/toolchain metadata into the context summary to satisfy the deep-export idea while building on the existing context export baseline (`README.md:68-70`, `improvement_ideas/LLMTK_TASKS_1.md:18-24`).
 
- [ ] Harden `llmtk stderr-thin` so it actually performs the template-chain collapsing, rule extraction, and
  optional SARIF/JSON dual output we advertise—right now the command exists, but the improvement note spells
  out the richer behavior that would materially improve signal for agents (`README.md:91-93`, `improvement_ideas/LLMTK_TASKS_1.md:30-37`).
  
- [ ] Version and formalize `exports/capabilities.json` with a `$schema` URL, per-tool feature flags, and latency hints so agents can negotiate features safely across releases, as suggested in the capabilities enhancement idea (`README.md:94-95`, `improvement_ideas/LLMTK_TASKS_1.md:39-41`).
  
  


