# Minimal CMake project used by the llmtk integration tests.
#
# It is intentionally tiny: a single executable target (so context export and
# deps have a real target to report) plus two CTest cases — one that always
# passes and one that always fails — implemented with `cmake -E true/false` so
# the test phase needs no build step or compiler beyond configuration.
cmake_minimum_required(VERSION 3.20)
project(llmtk_fixture CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_executable(hello src/main.cpp)

enable_testing()
add_test(NAME hello_passes COMMAND "${CMAKE_COMMAND}" -E true)
add_test(NAME hello_fails COMMAND "${CMAKE_COMMAND}" -E false)
