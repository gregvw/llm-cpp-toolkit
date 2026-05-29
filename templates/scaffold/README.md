# Project scaffold templates

Jinja2 templates rendered by `llmtk init` (see `llmtk/services/scaffold.py`).
These are the **only** thing llmtk templates — runtime JSON artifacts, MCP
responses, and capabilities output are generated in plain Python and must not be
templated.

Each template receives the same context (`ScaffoldContext`):

| variable            | type | source                                            |
|---------------------|------|---------------------------------------------------|
| `project_name`      | str  | positional `init` argument                        |
| `cpp_standard`      | str  | `--std` (default `17`)                            |
| `cmake_minimum`     | str  | `--cmake-min` (default `3.20`)                    |
| `target_type`       | str  | `"executable"` or `"library"` (from `--preset`)   |
| `enable_tests`      | bool | from `--preset`                                   |
| `enable_sanitizers` | bool | from `--preset`                                   |
| `pic`               | bool | position-independent code (from `--preset`)       |

`--preset` → profile mapping (`_PRESET_PROFILES` in `scaffold.py`):

| preset       | target_type | tests | sanitizers | pic |
|--------------|-------------|-------|------------|-----|
| `minimal`    | executable  | no    | no         | no  |
| `executable` | executable  | yes   | no         | no  |
| `library`    | library     | yes   | no         | yes |
| `full`       | executable  | yes   | yes        | no  |

Rendering uses `StrictUndefined`, so referencing a variable not listed above is
a hard error rather than a silent empty string. Keep generated CMake boring and
explicit.
