# Possible Improvements

- Fuzzer integration that exports minimized crashes and sanitizer traces in JSON or SARIF for agent consumption.
- WebAssembly and cross-compilation awareness, including Emscripten presets and multi-architecture toolchain exports.
- Enhanced reproducibility capture: snapshot environment variables, toolchain digests, and build inputs to enable deterministic rebuilds.
- Extended testing utilities: broaden security and quality gating (beyond SARIF severity) and integrate fuzz or test outputs into the context pack workflow.
