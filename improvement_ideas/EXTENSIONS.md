# Extensions

Use the Python package `simple-term-menu` to allow opt-in/opt-out of capabilities to be installed (or removed)

## Optional capabilities


### ModernCppStarter

Add `llmtk scaffold --from=ModernCppStarter` to clone or adopt an existing repo. Detect if the target already matches
its layout and fill in missing pieces like CI, clang format, coverage. Great for fast green-field demos. 

### Pitchform conventions

Add `llmtk scafford --pitchform` that lays out `/include`. `/src`, `/tests`, namespace foldering, and creates a 
Pitchfork-compatibe `CMakeLists.txt`. Our `context export --deep` already has the file-api info to validate the
structure. 

### Catch2/doctest/GoogleTest

Provide presets `llmtk testinit --framework=catch2|doctest|gtest` to drop a timy sample test, add a CTest target, and auto-enable
result export. 

### indicators

Progress bars/spinners.

- Use for `llmtk analyze --incremental,reduce,long` context pack runs.
- Benefits to agents: deterministic progress events (we emit JSON hooks) with human-friendly TTY UI when a user runs it.

### cxxopts

CLI parsing for sample tools and scaffolds.

- Use in demo binaries we scaffold so examples are idiomatic and easy to expand
- Agents recognize a stable CLI pattern for better automation.

### tabulate

Display pretty tables.

- Great for human-local runs. Summarize SARIF counts, cache hits, top warnings. 
- Pair with a `--json` mirror so agents still consume structured data. 

### ApprovalTests and rapidcheck

Excellent for CLI agents. They can propose diffs for failing approvals and regenerate baselines behind a flag. 
Opt-ins: `llmtk test init --property` or `--approval` to seed one example each and whow agents how to use them.
THes catch classes of bugs AI often misses. 


### Magic Enum

- Conversion between `enum` and string at compiler time. Iteration over enumerators. Bitflag helpers.
- Lets us *name* states, error codes, and config enums in logs/SARIF without brittle hand-kept tables. 

### nameof

- Compile-time retrieval of identifiers, variables, types, enums, members, and functions. 
- Eliminates hard-coded string literals in diagnostics and logs, keeping names in sync with the code. 

### Google Benchmark

Profile: `llmtk bench init` to add a microbenchmark tarket and `llmtk bench run --json` to emit run summaries into 
`exports/reports/bench.json` for agents to compare after fix-its.

### `{fmt}` + spdlog

Ship a tiny clang-tidy module/config that:

- Prefers `fmt::format` over iostreams in new code suggestions
- Provides IWYU mappings for spdlog's common headers to avoid include explosions.

### nlohmann/json and toml++

Detect presence and expose "parsing helpers" in the error knowledge base, e.g. for a failing parse, and
suggest `ordered_json`, `from_json` and `to_json` skeletons or `toml::parse_result` triage with examples. These
are hugely common in modern C++ repos and easy wins for agents. 

### simdjson

For large JSON files that sjow up in the repo. The deep context knows the file sizes. Recommend a 
drop-in benchmark scaffold (e.g. `llmtk bench add simdjson_vs_json33`) so agents can justify migrating hot paths. 

### Cpp-Taskflow

Add a recipe under `cookbook/` showing how to parallelize a build-step or data pipeline with a `tf::Taskflow` then
include a clang-tidy profile that flags accidental shared-state captures in lambdas, a common AI error.

### moodycamel::concurrentqueue

Inclue an IWYU mapping and a minimal stress test template that `llmtk test --json` can run under TSAN presets. 

### CPM (CMake Package Manager)

Streamline dependency management for project created with the toolkit. It's a lightweight, CMake-native approach that 
would integrate seamlessly with the existing CMake infrastructure, making it easier for AI agents to suggest and manage
external dependencies, 

### Polished UI 

Consider using the Python packages rich and textual to make a clean and polished-looking, user friendly interface.
