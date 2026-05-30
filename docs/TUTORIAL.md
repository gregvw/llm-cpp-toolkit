# Agent-Guided Tutorial

This walkthrough shows how to install **llm-cpp-toolkit**, scaffold a deliberately broken C++ project, and iterate with an LLM/agent to bring it back to green by leaning on the toolkit’s context packs, analyzers, and sanitized builds. Each stage calls out what the user does versus what the agent can automate once the artifacts exist.

```
┌────────────────────┐      ┌────────────────────┐
│ 1) User runs llmtk ├─────>│ 2) JSON artifacts  │
│ (build, analyze)   │      │  (exports/, logs/) │
└─────────┬──────────┘      └─────────┬──────────┘
          │                           │
          │                           V
┌─────────┴──────────┐      ┌─────────┴──────────┐
│ 4) User applies    ├<─────┤ 3) Agent proposes  │
│    the fix         │      │    a fix           │
└────────────────────┘      └────────────────────┘
```

In practice the agent can automate the inner loop—calling `llmtk`/`build_manager`/`cmake`, parsing the JSON, applying fixes, and repeating—until the build, sanitizers, and analyzers come back clean.

> 💡 Tip: The tutorial assumes you’re on Linux or macOS with a recent Clang/LLVM toolchain available. Substitute equivalent package commands if your distro differs.

## What You’ll Accomplish
- Install `llmtk` from the public repo and verify the environment with `llmtk doctor`.
- Generate a fresh CMake project (`buglab`) with `llmtk init`.
- Seed the project with code that contains both compile-time and runtime bugs.
- Produce context packs (`exports/…`) and filtered build logs that an agent can consume without guesswork.
- Let the agent drive fixes: first for compiler diagnostics, then for AddressSanitizer/UBSan findings, and finally for static-analysis cleanups.

## 0. Prerequisites
- Linux or macOS shell with `curl`, `python3`, `cmake`, and either `clang` or `gcc`.
- Optional but recommended: `ninja`, `clang-tidy`, `cppcheck`, `include-what-you-use`.
- Network access to download the installer (or clone the repo beforehand).

If you are running inside a minimal container, install the toolchain first, e.g.

```bash
sudo apt update && sudo apt install -y build-essential clang ninja-build python3 curl git
```

## 1. Install llm-cpp-toolkit
Pick the path that matches your setup. The zero-dependency Bash installer is the quickest way to get started:

```bash
curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash
llmtk --version
```

Other distributable options (Nix, Homebrew tap, Docker, etc.) are described in `docs/INSTALLATION.md`. Regardless of how you install, keep the repository handy—you may want to inspect the shipped presets or manifests later.

## 2. Run the Health Check
With `llmtk` on your `PATH`, verify the host before creating a project:

```bash
mkdir -p ~/llmtk-workshop
cd ~/llmtk-workshop
llmtk doctor
```

`exports/doctor.json` now contains a structured summary of the discovered toolchain. Share that file (or its JSON payload) with your agent so it immediately knows which compilers and analyzers are available.

## 3. Scaffold a Playground Project
Create a new project named `buglab` using the `full` preset. It scaffolds a single `buglab` executable with explicit warnings (`-Wall -Wextra -Wpedantic`) and AddressSanitizer + UndefinedBehaviorSanitizer wired into **Debug** builds:

```bash
llmtk init buglab --preset full
cd buglab
```

`llmtk init` renders the project from templates under `templates/scaffold/`: a `CMakeLists.txt`, a starter `src/main.cpp`, a `.gitignore`, and a `CMakePresets.json` exposing a `default` configure preset (Ninja, Debug). It also writes `exports/capabilities.json` so agents can enumerate supported commands without scraping docs.

> The `full` preset bakes the sanitizers into the single `buglab` target for Debug builds — there are no separate `buglab_asan_ubsan`/`buglab_tsan` targets. You opt into the sanitizers by configuring a Debug build (below).

## 4. Verify the Build Manager CLI
The installer drops a companion CLI named `build_manager` into the same prefix as `llmtk`. It wraps `cmake` configure/build/test and writes concise JSON summaries under `logs/` that are engineered for agents. Confirm it’s available:

```bash
build_manager --help | head
```

You should see the usage banner with `configure`, `build`, `test`, and `full` subcommands. `build_manager` does not inject extra flags — it builds whatever the project’s CMake cache is configured with, so we control strictness and sanitizers through the `cmake` configure step in the next sections.

## 5. Seed Some Bugs
Replace the generated `src/main.cpp` with intentionally problematic code. It contains:
- a `double` → `std::uint8_t` narrowing conversion that `-Wconversion -Werror` will reject,
- an out-of-bounds loop that reads past the end of a vector,
- a heap buffer overflow that AddressSanitizer will flag at runtime.

```bash
cat <<'CODE' > src/main.cpp
#include <cstdint>
#include <iostream>
#include <vector>

std::uint8_t scale(double value) {
    return value * 1.5; // implicit narrowing double -> uint8_t (error under -Wconversion -Werror)
}

double average(const std::vector<int>& values) {
    if (values.empty()) {
        return 0.0;
    }

    int sum = 0;
    for (std::size_t i = 0; i <= values.size(); ++i) { // oops: off-by-one read
        sum += values[i];
    }

    return static_cast<double>(sum) / static_cast<double>(values.size());
}

int main() {
    std::vector<int> data{1, 2, 3};
    const double avg = average(data);
    std::cout << "Average: " << avg << "\n";
    std::cout << "Scaled:  " << static_cast<int>(scale(avg)) << "\n";

    int* buffer = new int[3];
    buffer[3] = 42; // heap overflow
    delete[] buffer;

    return 0;
}
CODE
```

## 6. Export Context for the Agent
Populate the compile database and CMake file API so `llmtk analyze` and external tools have something to chew on:

```bash
llmtk context export --build build
# Add --deep to capture target + toolchain summaries for agents
# llmtk context export --build build --deep
```

Artifacts you can hand to the agent now include:
- `exports/compile_commands.json`
- `exports/cmake-file-api/`
- `exports/context.json` (a rollup with timestamps and paths)

## 7. First Iteration — Fix the Compile Failure
The `full` preset’s warnings (`-Wall -Wextra -Wpedantic`) won’t reject the narrowing on their own, so configure a strict **Debug** build that promotes conversion warnings to errors. This is also the configuration that enables the sanitizers for the next step:

```bash
cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_CXX_FLAGS="-Wall -Wextra -Wconversion -Werror"
build_manager build          # or: cmake --build build
```

Expect a non-zero exit, with a JSON log under `logs/` (e.g. `logs/build_*.json`) capturing compiler diagnostics such as:

```json
{
  "type": "compiler_diagnostic",
  "severity": "error",
  "file": "src/main.cpp",
  "message": "implicit conversion turns floating-point number into integer: 'double' to 'std::uint8_t' [-Werror,-Wfloat-conversion]"
}
```

**Agent playbook:**
1. Inspect `logs/build_*.json` (or the console summary) to pinpoint the failing diagnostic.
2. Propose a minimal patch — make the conversion explicit, e.g. `return static_cast<std::uint8_t>(value * 1.5);` (or `std::lround(value * 1.5)` if you want rounding).
3. Have the user apply the patch and rerun `build_manager build` until the compile stage succeeds.

Once the build passes, the manager reports success. The binary now links the sanitizers (Debug) — time to run it.

## 8. Second Iteration — Catch the Runtime Crash
Because you configured a Debug build, the single `buglab` binary is already instrumented with AddressSanitizer and UBSan — there is no separate sanitizer target to build. Just run it:

```bash
ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=print_stacktrace=1 ./build/buglab
```

You should see output similar to:

```
==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address ...
READ of size 4 at ... in average(...) src/main.cpp
```

(The off-by-one read in `average` trips first; once that’s fixed, the `buffer[3]` write is the next overflow ASan reports.)

**Agent playbook:**
1. Parse the sanitizer report (from stdout/stderr, or tee it into `exports/sanitizers/asan.log`).
2. Identify the two memory issues: the loop’s `<=` bound and the `buffer[3]` write.
3. Recommend patches (tighten the loop condition, fix the buffer indexing, optionally replace the raw `new[]/delete[]` with `std::vector<int>`).
4. After applying the fixes, rebuild (`build_manager build`) and rerun the binary to confirm the crash is gone.

> On macOS, running an ASan binary may require the Clang runtime to be discoverable by `dyld`; on Linux the report prints directly. Either way the bug is the same — the agent reasons from the sanitizer text.

## 9. Third Iteration — Static Analysis Cleanup
With the program building cleanly and sanitizers quiet, run the analyzer suite to ensure there are no lingering findings:

```bash
llmtk analyze src/main.cpp
```

The command emits JSON reports under `exports/reports/` for clang-tidy, IWYU, and cppcheck. Hand them to the agent so it can double-check that no warnings remain. If clang-tidy suggests style or safety improvements (e.g. using `std::size_t` consistently), fold them in and rerun the command.

## 10. Wrap-Up and Next Steps
- Regenerate the project capabilities summary after major changes:

  ```bash
  llmtk capabilities
  ```

- Capture a final build/test transcript for provenance:

  ```bash
  build_manager full                          # configure + build + test, JSON-logged
  llmtk context export --build build --deep   # refresh context after fixes
  llmtk analyze src/main.cpp
  ```

- Want a different sanitizer? Configure a separate build directory with the flags you need, e.g. ThreadSanitizer. Use a **non-Debug** config so TSan isn't combined with the `full` preset's Debug ASan/UBSan — AddressSanitizer and ThreadSanitizer are mutually exclusive:

  ```bash
  cmake -S . -B build-tsan -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DCMAKE_CXX_FLAGS="-fsanitize=thread" \
        -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=thread"
  cmake --build build-tsan && ./build-tsan/buglab
  ```

- Share the updated `exports/` directory and `logs/` folder with your agent. They are intentionally machine-readable so any LLM can resume work without rerunning expensive steps.

From here you can evolve `buglab` into a richer playground—add CTest cases, gate the loop in CI on `llmtk preflight`/`llmtk analyze`, or wrap the whole thing in `llmtk agent mcp` so an MCP-capable agent drives it. The key pattern is the same: keep artifacts deterministic, keep outputs in `exports/`, and let the agent reason from the JSON instead of raw terminal scrollback.
