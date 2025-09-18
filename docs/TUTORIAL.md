# Agent-Guided Tutorial

This walkthrough shows how to install **llm-cpp-toolkit**, scaffold a deliberately broken C++ project, and iterate with an LLM/agent to bring it back to green by leaning on the toolkit’s context packs, analyzers, and sanitized builds. Each stage calls out what the user does versus what the agent can automate once the artifacts exist.

> 💡 Tip: The tutorial assumes you’re on Linux or macOS with a recent Clang/LLVM toolchain available. Substitute equivalent package commands if your distro differs.

## What You’ll Accomplish
- Install `llmtk` from the public repo and verify the environment with `llmtk doctor`.
- Generate a fresh CMake project (`buglab`) that follows the guidance encoded in `llmtk init`.
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
Create a new project named `buglab` using the full preset, which wires strict warnings, sanitizer targets, and lint presets:

```bash
llmtk init buglab --preset=full
cd buglab
```

The command writes a CMakeLists.txt aligned with `CMAKE_GUIDANCE.md`, a starter `main.cpp`, and regenerates `exports/capabilities.json` so agents can enumerate supported commands without scraping docs.

## 4. Verify the Build Manager CLI
The installer drops a companion CLI named `build_manager` into the same prefix as `llmtk`. It wraps configure/build/test with concise JSON summaries engineered for agents. Confirm it’s available, then you can call it from anywhere:

```bash
build_manager --help | head
```

You should see the usage banner with `configure`, `build`, `test`, `clean`, and `full` subcommands.

## 5. Seed Some Bugs
Replace the generated `main.cpp` with intentionally problematic code. It contains:
- a `double` → `int` narrowing conversion that trips `-Wconversion` (treated as an error),
- an out-of-bounds loop that will corrupt memory,
- a heap buffer overflow that AddressSanitizer will flag once the code builds.

```bash
cat <<'CODE' > main.cpp
#include <cstdint>
#include <iostream>
#include <vector>

std::uint8_t scale(double value) {
    return value * 1.5; // implicit narrowing conversion (will be -Werror)
}

double average(const std::vector<int>& values) {
    if (values.empty()) {
        return 0.0;
    }

    int sum = 0;
    for (std::size_t i = 0; i <= values.size(); ++i) { // oops: off-by-one
        sum += values[i];
    }

    auto truncated = scale(sum);
    return static_cast<double>(truncated) / values.size();
}

int main() {
    std::vector<int> data{1, 2, 3};
    std::cout << "Average: " << average(data) << "\n";

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
```

Artifacts you can hand to the agent now include:
- `exports/compile_commands.json`
- `exports/cmake-file-api/`
- `exports/context.json` (a rollup with timestamps and paths)

## 7. First Iteration — Fix the Compile Failure
Run a full configure/build cycle with the build manager. The strict warning set will stop the build on the implicit narrowing conversion:

```bash
build_manager full --no-tests
```

Expect a non-zero exit along with a log under `logs/`, e.g. `logs/build_20240830_153011.json`. The JSON captures compiler diagnostics such as:

```json
{
  "type": "compiler_diagnostic",
  "severity": "error",
  "file": "main.cpp",
  "line": 6,
  "column": 12,
  "message": "conversion from 'double' to 'std::uint8_t' may change value"
}
```

**Agent playbook:**
1. Inspect `logs/build_*json` (or the console summary) to pinpoint the failing diagnostic.
2. Propose a minimal patch—e.g. change `scale` to return `double`, or switch to `std::lround` with a checked cast.
3. Have the user apply the patch and rerun `build_manager full --no-tests` until the compile stage succeeds.

Once the build passes, the manager prints `✅ Build successful`. Sanitized targets still haven’t run—next!

## 8. Second Iteration — Catch the Runtime Crash
AddressSanitizer and UBSan variants are available out of the box thanks to the preset. Build and execute the ASan/UBSan clone of the target:

```bash
cmake --build build --target buglab_asan_ubsan
ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=print_stacktrace=1 ./build/buglab_asan_ubsan
```

You should see output similar to:

```
==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address ...
READ of size 4 at ... main.cpp:25
```

**Agent playbook:**
1. Parse the sanitizer report (either from stdout or by tee’ing it into `exports/sanitizers/asan.log`).
2. Identify the two memory issues: the loop’s `<=` bound and the `buffer[3]` write.
3. Recommend patches (tighten the loop condition, fix the buffer indexing, optionally replace the raw `new[]/delete[]` with `std::vector<int>`).
4. After applying the fixes, rebuild and rerun the sanitized binary to confirm the crash is gone.

## 9. Third Iteration — Static Analysis Cleanup
With the program building cleanly and sanitizers quiet, run the analyzer suite to ensure there are no lingering findings:

```bash
llmtk analyze main.cpp
```

The command emits JSON reports under `exports/reports/` for clang-tidy, IWYU, and cppcheck. Hand them to the agent so it can double-check that no warnings remain. If clang-tidy suggests style or safety improvements (e.g. using `std::size_t` consistently), fold them in and rerun the command.

## 10. Wrap-Up and Next Steps
- Regenerate the project capabilities summary after major changes:

  ```bash
  llmtk capabilities
  ```

- Capture a final build/test transcript for provenance:

  ```bash
  build_manager full
  cmake --build build --target buglab_tsan    # optional: thread sanitizer
  llmtk context export --build build          # refresh context after fixes
  llmtk analyze .
  ```

- Share the updated `exports/` directory and `logs/` folder with your agent. They are intentionally machine-readable so any LLM can resume work without rerunning expensive steps.

From here you can evolve `buglab` into a richer playground—add unit tests, wire `llmtk reduce` around failing cases, or script the whole loop in CI. The key pattern is the same: keep artifacts deterministic, keep outputs in `exports/`, and let the agent reason from the JSON instead of raw terminal scrollback.
