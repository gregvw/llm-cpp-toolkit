# Editor Integrations

This directory ships lightweight adapter stubs so editors and agent shells can attach to the llmtk Model Context Protocol endpoint without bespoke glue code. Each file is intentionally small—treat them as starting points and tailor paths, environment variables, and timeout policies to your workspace.

## Cursor

- File: `integrations/cursor/llmtk-tool.json`
- Copy to `~/.cursor-tools.json` (or merge with your existing manifest).
- Cursor will launch `llmtk agent mcp` in the workspace root and expose the toolkit as an MCP tool named `llmtk`.

## Continue

- File: `integrations/continue/llmtk-tool.json`
- Merge into your Continue `config.json` under the top-level `tools` key.
- Continue will spawn `llmtk agent mcp` inside the current workspace folder.

## Aider

- File: `integrations/aider/llmtk-tool.yaml`
- Place under `~/.config/aider/tools.d/` and restart aider.
- Aider (>= 0.50) detects the MCP tool and routes file/system requests through llmtk.

All three adapters forward the `LLMTK_BOOTSTRAP_USE_SOURCE` environment variable so development builds prefer the local checkout over published releases. Remove it when running against an installed copy.

If your editor expects TCP sockets instead of stdio you can pair the same configs with `llmtk agent serve --port 8765`; the MCP variant remains the canonical, manifest-driven surface.
