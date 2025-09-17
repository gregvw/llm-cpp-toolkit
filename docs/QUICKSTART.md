# Quickstart

- Ensure core tools exist: `cmake`, `ninja` (others optional).
- Use the CLI from the repo root:

```
python3 cli/llmtk doctor
python3 cli/llmtk context export --build build
python3 cli/llmtk analyze src/ include/
```

Artifacts are written under `exports/` for easy parsing by agents.

