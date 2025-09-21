### **Project Title: `TextProcessor`**

**Objective:**

Create a command-line C++ application named `TextProcessor` that reads a text file, performs a set of text transformations, and prints the result to standard output. The project must be built using CMake and include unit tests.

**Core Requirements:**

1.  **Application Name:** `TextProcessor`
2.  **Language:** C++17
3.  **Build System:** CMake (minimum version 3.16)
4.  **Dependencies:** None outside the C++ Standard Library.
5.  **Licensing:** The project should be licensed under the MIT License.

**Functional Requirements:**

1.  The application shall accept exactly one command-line argument: the path to an input text file.
2.  If the application is run with zero or more than one argument, it should print a usage message to `stderr` and exit with a non-zero status code.
    *   Usage message: `Usage: TextProcessor <input_file>`
3.  If the specified input file cannot be opened, the application should print an error message to `stderr` and exit with a non-zero status code.
    *   Error message: `Error: Could not open file <input_file>`
4.  The application shall read the entire content of the input file.
5.  The application shall perform the following transformations on the text:
    *   Convert the entire text to uppercase.
    *   Reverse the entire text (e.g., "HELLO" becomes "OLLEH").
    *   Count the number of words in the original text (words are separated by whitespace).
6.  The application shall print the following to standard output:
    *   The transformed (uppercased and reversed) text.
    *   The word count on a new line, in the format: `Word count: <count>`

**Example:**

If `input.txt` contains: `Hello world, this is a test.`

Running `./TextProcessor input.txt` should produce the following output:

```
.TSET A SI SIHT ,DLROW OLLEH
Word count: 6
```

**Project Structure:**

The project should have the following directory structure:

```
TextProcessor/
├── CMakeLists.txt
├── LICENSE
├── README.md
├── src/
│   ├── main.cpp
│   └── text_processor.cpp
│   └── text_processor.h
└── tests/
    ├── CMakeLists.txt
    └── test_text_processor.cpp
```

**Source Code Design:**

*   **`src/main.cpp`**: This file should contain the `main` function, handle command-line argument parsing, file I/O, and call the text processing functions.
*   **`src/text_processor.h`**: This file should declare the functions that perform the text transformations.
    *   `std::string to_uppercase(const std::string& text);`
    *   `std::string reverse_text(const std::string& text);`
    *   `int count_words(const std::string& text);`
*   **`src/text_processor.cpp`**: This file should implement the functions declared in `text_processor.h`.

**Build Requirements (CMake):**

*   The root `CMakeLists.txt` should define the project, set the C++ standard to 17, and add the `src` and `tests` subdirectories.
*   The `src/` directory's sources should be included by the root `CMakeLists.txt` to build the `TextProcessor` executable.
*   The `tests/` directory should contain a `CMakeLists.txt` that defines a test executable.
*   The project should use `FetchContent` to download and link GoogleTest for the unit tests.
*   The main executable should be named `TextProcessor`.
*   The test executable should be named `run_tests`.
*   Enable warnings (`-Wall`, `-Wextra`, `-Wpedantic`).

**Testing Requirements:**

*   The `tests/test_text_processor.cpp` file should contain unit tests for the functions in `text_processor.cpp`.
*   At a minimum, there should be tests for:
    *   `to_uppercase` with a sample string.
    *   `reverse_text` with a sample string.
    *   `count_words` with a sample string containing multiple words and spaces.
    *   `count_words` with an empty string.

**Documentation:**

*   **`README.md`**: A brief description of the project, how to build it, and how to run it.
*   **`LICENSE`**: The full text of the MIT License.
---
