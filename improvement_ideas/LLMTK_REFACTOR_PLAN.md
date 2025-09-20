# Refactor Plan

- Turn cli/llmtk into a thin shim that only wires argparse and delegates to llmtk.cli.main(); migrate the global path/version setup now in cli/
llmtk:1-120 into llmtk/core/context.py so installers keep the same entry point while other modules can import shared state safely.
- Split the dry-run, filesystem, and process helpers clustered at `cli/llmtk:16-150` into `llmtk/core/dry_run.py`, `llmtk/core/fs.py`, and `llmtk/core/process.py`
- Move `config/telemetry` persistence from `cli/llmtk:96-170` into `llmtk/core/config.py` to eliminate duplicate IO logic across commands.
- Collect `manifest/CMake` utilities (`validate_cmake_guidance`, `load_yaml`, `generate_reference_md`, `generate_capabilities_json` at `cli/llmtk:200-420`) into `llmtk/services/manifest.py` and `llmtk/services/cmake.py`, and add a thin adapter module around the optional template engine so `cmd_init` can
stay compact.
- Restructure the command implementations by domain under `llmtk/commands/`: e.g. `init.py` (`cmd_init/adoption` docs at `cli/llmtk:1180-1840`),
`doctor.py` (`cli/llmtk:1861-2025`), `context.py` (`cli/llmtk:2030-2250`), `analyze.py` (`cli/llmtk:2191-2940`), `test.py` (`cli/llmtk:2537-2670`), `bench.py` (`cli/llmtk:2672-3130`), `diagnostics.py` for `stderr-thin/tidy` (`cli/llmtk:2942-3360`), plus smaller modules for `install`, `telemetry`, `cache`, `kb`, and agent commands (`cli/llmtk:3459-4382`); each module should expose register(subparsers) to keep files ≤300 lines.
- Share cross-cutting helpers through focused service modules: `llmtk/services/testing.py` for CTest preview/parsing (`cli/llmtk:430-720` & `cli/llmtk:2420-2660`), `llmtk/services/analysis.py` for `clang-tidy/IWYU/cppcheck` orchestration (`cli/llmtk:2260-2940`), `llmtk/services/diagnostics.py` for stderr thinning (`cli/llmtk:2942-3277`), and `llmtk/services/telemetry.py` for JSONL logging (`cli/llmtk:3888-3950`).
- Execute the migration incrementally: introduce the new package scaffolding, add a registry-driven CLI that imports one moved command at a
time, `run llmtk <cmd> --help` and targeted smoke tests after each move, and finish with documentation updates describing the new module layout.

## Next Steps

1. Scaffold `llmtk/core` and `llmtk/commands/__init__.py`, adjust `cli/llmtk` to call the new entrypoint, and verify with `llmtk --help`.
2. Migrate the `init/docs/capabilities` commands first to validate the registration pattern, then iterate through the remaining command groups.
3. Add lightweight `unit/smoke` tests for the core service modules and ensure `exports/*.json` outputs remain identical before tackling deeper
feature work.

