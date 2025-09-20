# Privacy & Telemetry

`llmtk` ships with privacy-conscious defaults. Telemetry is **disabled by default** and
is only recorded after an explicit opt-in. When enabled, events are saved locally to help
you understand how the toolkit is used across commands and to debug automation flows.

## What Gets Recorded

Each successful command invocation appends a single JSON line to
`~/.local/share/llmtk/telemetry.jsonl` (or the directory specified by
`LLMTK_DATA_HOME`). The payload contains:

- anonymous telemetry identifier (random UUID stored in `~/.config/llmtk/config.json`)
- command name and resolved subcommand (e.g. `context` / `export`)
- exit code and whether `--dry-run` was active
- execution duration in milliseconds
- toolkit version and hashed workspace identifier (`sha256(cwd)[:12]`)

No source paths, command arguments, environment variables, or user-provided strings are
captured. The file never leaves your machine and is suitable for review or git archival
if you want to correlate agent behaviour with toolkit activity.

## Opting In or Out

Use the built-in `telemetry` command:

```bash
llmtk telemetry status   # show current state and log location
llmtk telemetry enable   # opt in to local telemetry collection
llmtk telemetry disable  # stop recording new events
llmtk telemetry purge    # delete the log and reset preferences
```

Enabling telemetry persists the preference under the directory reported by
`LLMTK_CONFIG_HOME` (defaults to `~/.config/llmtk`). Disabling stops further writes but
retains existing logs until you run `llmtk telemetry purge`.

## Dry-Run Mode

Global preview mode (`llmtk --dry-run ...`) skips external process execution and file
writes wherever possible. When telemetry is enabled, dry-run invocations are detected
but suppressed—no telemetry line is appended, and a `[dry-run] telemetry event
(suppressed write)` message is emitted instead. Preview sessions therefore leave no
trace on disk.

## Customising Storage Locations

Two environment variables control where preferences and logs live:

- `LLMTK_CONFIG_HOME` – overrides the directory used for configuration state
- `LLMTK_DATA_HOME` – overrides the directory that receives telemetry logs

Both follow XDG defaults when unset (`~/.config/llmtk` and `~/.local/share/llmtk`).

## Disabling Programmatic Access

Agents interacting through `llmtk agent` respect the same telemetry settings. If you do
not opt in, agent-driven runs will not generate telemetry either. Commands invoked with
`--dry-run` never mutate telemetry state, even when a session is otherwise enabled.

For teams that do not wish to expose telemetry at all, simply avoid calling
`llmtk telemetry enable` or distribute a pre-populated config file with
`{"telemetry": {"enabled": false}}`.
