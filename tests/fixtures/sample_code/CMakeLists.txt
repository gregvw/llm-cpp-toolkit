cmake_minimum_required(VERSION 3.14)
project(llmtk_test_fixtures VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Test files with various issues
add_executable(test_nullptr test_nullptr.cpp)
add_executable(test_memory test_memory.cpp)
add_executable(test_includes test_includes.cpp)

# Enable warnings
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(test_nullptr PRIVATE -Wall -Wextra)
    target_compile_options(test_memory PRIVATE -Wall -Wextra)
    target_compile_options(test_includes PRIVATE -Wall -Wextra)
endif()
