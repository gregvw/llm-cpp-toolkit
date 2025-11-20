// Sample C++ code with memory and pointer issues
// Expected to trigger: cppcheck errors, clang-tidy warnings

#include <cstdlib>
#include <cstring>

void null_pointer_dereference() {
    // Should trigger: cppcheck nullPointer
    int* ptr = nullptr;
    *ptr = 42;  // Line 9 - Null pointer dereference
}

void uninitialized_variable() {
    // Should trigger: cppcheck uninitvar
    int value;
    int result = value + 10;  // Line 15 - Using uninitialized variable
}

void memory_leak() {
    // Should trigger: cppcheck memleak
    int* data = new int[100];
    // Missing delete[] - Line 20
    return;  // Memory leak here
}

void buffer_overflow() {
    // Should trigger: various warnings
    char buffer[10];
    strcpy(buffer, "This string is definitely too long for the buffer");  // Line 27
}

void use_after_free() {
    // Should trigger: warnings about use after free
    int* ptr = new int(42);
    delete ptr;
    *ptr = 100;  // Line 34 - Use after free
}

void correct_memory_usage() {
    // This is correct
    int* ptr = new int(42);
    if (ptr != nullptr) {
        int value = *ptr;
        delete ptr;
        ptr = nullptr;
    }
}
