#include "handler/error_detection.h"

#include <algorithm>
#include <cctype>
#include <iostream>

namespace handler {

namespace {
bool containsInsensitive(const std::string& text, const std::string& needle) {
    std::string a = text;
    std::string b = needle;
    std::transform(a.begin(), a.end(), a.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    std::transform(b.begin(), b.end(), b.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return a.find(b) != std::string::npos;
}
}

std::vector<DetectedError> detectErrors(const std::string& text) {
    std::vector<DetectedError> errors;
    auto add = [&](const char* category, const char* summary, int confidence) {
        errors.push_back({category, summary, text, confidence});
    };

    if (containsInsensitive(text, "modulenotfounderror") || containsInsensitive(text, "cannot find module")) {
        add("MISSING_MODULE", "A required module/package appears to be missing.", 95);
    }
    if (containsInsensitive(text, "command not found") || containsInsensitive(text, "is not recognized as an internal or external command")) {
        add("MISSING_COMMAND", "A required command/tool was not found.", 95);
    }
    if (containsInsensitive(text, "dependency conflict") || containsInsensitive(text, "conflicting dependencies") ||
        (containsInsensitive(text, "requires") && containsInsensitive(text, "but you have"))) {
        add("DEPENDENCY_CONFLICT", "Dependency requirements appear incompatible.", 90);
    }
    if (containsInsensitive(text, "permission denied") || containsInsensitive(text, "access is denied")) {
        add("PERMISSION", "The operation appears to lack required permission.", 92);
    }
    if (containsInsensitive(text, "address already in use") || containsInsensitive(text, "eaddrinuse")) {
        add("RESOURCE_CONFLICT", "A requested network port/resource is already in use.", 92);
    }
    return errors;
}

void printDetectedErrors(const std::vector<DetectedError>& errors) {
    if (errors.empty()) {
        std::cout << "No known Handler error pattern detected.\n";
        return;
    }
    std::cout << "Detected errors:\n";
    for (const auto& error : errors) {
        std::cout << "  [" << error.category << "] " << error.summary
                  << " (confidence " << error.confidence << "%)\n";
    }
}

} // namespace handler
