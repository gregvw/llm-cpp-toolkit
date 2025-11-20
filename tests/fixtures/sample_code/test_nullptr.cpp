// Sample C++ code with nullptr modernization issues
// Expected to trigger: clang-tidy modernize-use-nullptr

#include <cstddef>

void use_null_macro() {
    // Should trigger: modernize-use-nullptr
    int* ptr1 = NULL;  // Line 8
    char* ptr2 = NULL; // Line 9

    if (ptr1 != NULL) {  // Line 11
        *ptr1 = 42;
    }
}

void use_zero_literal() {
    // Should trigger: modernize-use-nullptr
    int* ptr3 = 0;     // Line 17
    void* ptr4 = 0;    // Line 18

    if (ptr3 == 0) {   // Line 20
        ptr3 = 0;      // Line 21
    }
}

void correct_usage() {
    // This is correct, no warnings expected
    int* ptr5 = nullptr;

    if (ptr5 != nullptr) {
        *ptr5 = 100;
    }
}
