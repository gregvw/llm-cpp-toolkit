// Sample C++ code with include issues
// Expected to trigger: include-what-you-use suggestions

#include <iostream>     // Used
#include <vector>       // Used
#include <string>       // Used
#include <map>          // NOT USED - should suggest removal
#include <set>          // NOT USED - should suggest removal
#include <algorithm>    // NOT USED - should suggest removal

// Missing: <memory> for std::unique_ptr - should suggest adding

void print_vector() {
    std::vector<int> numbers = {1, 2, 3, 4, 5};

    for (int num : numbers) {
        std::cout << num << " ";
    }
    std::cout << std::endl;
}

void use_string() {
    std::string message = "Hello, IWYU!";
    std::cout << message << std::endl;
}

// This would require <memory> but it's commented out to avoid compilation errors
// std::unique_ptr<int> create_unique() {
//     return std::make_unique<int>(42);
// }

int main() {
    print_vector();
    use_string();
    return 0;
}
