# Recommended CMake Strategy

```cmake
cmake_minimum_required(VERSION 3.28)
project(MyProject LANGUAGES CXX)

# Always declare the language level once
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Export compile_commands.json (handy for your reducer or tools)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# 1) Warnings-as-errors & friends — per-compiler, per-config, target-attachable
add_library(project_warnings INTERFACE)

if (MSVC)
  target_compile_options(project_warnings INTERFACE
    /W4 /WX /permissive- /Zc:preprocessor /Zc:__cplusplus /EHsc
    # optional noise trims:
    # /wd4244 /wd4267
  )
else()
  target_compile_options(project_warnings INTERFACE
    -Wall -Wextra -Wconversion -Wshadow -Werror
    -Wnon-virtual-dtor -Woverloaded-virtual -Wimplicit-fallthrough
    -fdiagnostics-show-option
  )
endif()

# 2) Sanitizers toggles (don’t hardcode CMAKE_CXX_FLAGS_*; compose options instead)
option(ENABLE_ASAN "Enable AddressSanitizer" $<NOT:$<CXX_COMPILER_ID:MSVC>>)
option(ENABLE_UBSAN "Enable UBSan"           $<NOT:$<CXX_COMPILER_ID:MSVC>>)
add_library(project_sanitizers INTERFACE)
if (NOT MSVC)
  if (ENABLE_ASAN)
    target_compile_options(project_sanitizers INTERFACE -fsanitize=address)
    target_link_options(project_sanitizers    INTERFACE -fsanitize=address)
  endif()
  if (ENABLE_UBSAN)
    target_compile_options(project_sanitizers INTERFACE -fsanitize=undefined)
    target_link_options(project_sanitizers    INTERFACE -fsanitize=undefined)
  endif()
endif()

# 3) Your target(s)
add_executable(my_app main.cpp)
target_link_libraries(my_app PRIVATE project_warnings project_sanitizers)

# 4) LLM-focused “lint” that compiles TUs with tight diagnostics (no linking)
#    Important: use the *same* include dirs/defs/opts as my_app so headers resolve.
get_target_property(MYAPP_SOURCES my_app SOURCES)
get_target_property(MYAPP_INCLUDES my_app INCLUDE_DIRECTORIES)
get_target_property(MYAPP_DEFS     my_app COMPILE_DEFINITIONS)
get_target_property(MYAPP_OPTS     my_app COMPILE_OPTIONS)

# Compose include and define flags portably for non-MSVC compilers.
set(_lint_includes "")
foreach(inc ${MYAPP_INCLUDES})
  list(APPEND _lint_includes -I${inc})
endforeach()

set(_lint_defines "")
foreach(def ${MYAPP_DEFS})
  list(APPEND _lint_defines -D${def})
endforeach()

# Build a response file so the command stays short (token-cheap logs)
set(_lint_rsp "${CMAKE_BINARY_DIR}/lint_args.rsp")
file(WRITE  "${_lint_rsp}" "")
foreach(opt ${MYAPP_OPTS})
  file(APPEND "${_lint_rsp}" "${opt}\n")
endforeach()
foreach(def ${_lint_defines})
  file(APPEND "${_lint_rsp}" "${def}\n")
endforeach()
foreach(inc ${_lint_includes})
  file(APPEND "${_lint_rsp}" "${inc}\n")
endforeach()
# Common warnings from the interface lib are already in MYAPP_OPTS.

# Pick flags per compiler
if (CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
  set(LINT_CORE_FLAGS
    -std=c++23 -fsyntax-only
    -Wfatal-errors -ferror-limit=1
    -ftemplate-backtrace-limit=6 -fconstexpr-backtrace-limit=3 -fmacro-backtrace-limit=2
    -fno-caret-diagnostics -fdiagnostics-color=never -fdiagnostics-show-option
    -fdiagnostics-format=json
  )
elseif (CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  set(LINT_CORE_FLAGS
    -std=c++20 -fsyntax-only
    -Wfatal-errors -fmax-errors=1
    -fconcepts-diagnostics-depth=2
    -fno-diagnostics-show-caret -fdiagnostics-color=never
    -fdiagnostics-format=json
  )
else()
  # MSVC: fall back to /analyze JSON? For now: no-op lint with success.
  set(LINT_CORE_FLAGS "")
endif()

# One lint target that iterates all TU’s; writes a single JSON per TU into build/lint/
add_custom_target(lint
  COMMENT "Running tight JSON diagnostics per translation unit..."
)
foreach(src ${MYAPP_SOURCES})
  get_filename_component(src_name "${src}" NAME_WE)
  set(out_json "${CMAKE_BINARY_DIR}/lint/${src_name}.json")
  file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/lint")
  add_custom_command(TARGET lint POST_BUILD
    COMMAND ${CMAKE_CXX_COMPILER} "@${_lint_rsp}" ${LINT_CORE_FLAGS} "${src}" 2> "${out_json}"
    BYPRODUCTS "${out_json}"
    COMMENT "Lint ${src_name}"
    VERBATIM
  )
endforeach()
```

Why these changes help:

* **Target-scoped warnings/sanitizers**: attach via INTERFACE libs; scale to many targets; avoid stomping global `CMAKE_CXX_FLAGS_*`.
* **Cross-compiler**: MSVC gets `/W4 /WX`, Clang/GCC get `-W*` without breaking Windows builds.
* **Sanitizers**: use `target_link_options` too (you need them at link time). Toggle by option instead of hardcoding Debug only.
* **Tight diagnostics**: `-fsyntax-only`, error/backtrace limits, and JSON keep logs tiny and consistent with your reducer.
* **Accurate linting**: the lint compiles each TU with the *same* includes/defs/options as the real target, so you don’t get false negatives from missing headers.
* **Response file**: keeps the command line short and reproducible; also reduces accidental token sprawl if you ever surface the command to an agent.
* **Per-TU JSON**: easiest for a reducer to consume; you can merge or just feed the first non-✅ to the LLM.

Nice extras (optional):

* Prefer **CMakePresets.json** for one-liners like `cmake --preset clang-debug` and to pin compilers.
* Add a second target `lint+expand` that bumps `-ftemplate-backtrace-limit` a bit when the model fails on the first pass.
* Emit **fix-its**: add Clang’s `-fdiagnostics-parseable-fixits` to `LINT_CORE_FLAGS` and have your reducer propose diffs.
* For multi-config generators (Visual Studio, Ninja Multi-Config), don’t rely on `CMAKE_BUILD_TYPE`; use presets or `--config Debug/Release`.

Usage stays the same as you wrote, with the bonus that `lint` now works for any number of source files and any include graph, and it produces clean, token-cheap JSON your reducer can digest.

