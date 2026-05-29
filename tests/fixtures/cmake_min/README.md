# cmake_min fixture

A minimal, buildable CMake project used by `tests/test_integration.py` to
exercise the stable llmtk agent backend (context export, deps, and CTest) end
to end.

- `src/main.cpp` — a small, valid C++ translation unit built as the `hello`
  target. It doubles as the known-good input for the `preflight` tests.
- Two CTest cases are registered with `cmake -E true` / `cmake -E false` so the
  passing/failing test paths are deterministic and require no build step.

The known-*bad* preflight input is written into a throwaway copy of this
fixture at test time (see `BAD_SOURCE` in the test module), so no intentionally
broken source file is committed to the repository.

Integration tests copy this directory into a temporary location before
configuring, so nothing here is mutated in place.
