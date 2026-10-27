#include "handler/verification.h"

#include <filesystem>
#include <iostream>

namespace handler {

VerificationResult verifyFileExists(const std::string& path) {
    const bool exists = std::filesystem::is_regular_file(path);
    return {exists, "file-exists", exists ? "file exists" : "file is missing"};
}

VerificationResult verifyDirectoryExists(const std::string& path) {
    const bool exists = std::filesystem::is_directory(path);
    return {exists, "directory-exists", exists ? "directory exists" : "directory is missing"};
}

void printVerification(const VerificationResult& result) {
    std::cout << "[" << (result.passed ? "PASS" : "FAIL") << "] "
              << result.check << ": " << result.details << '\n';
}

} // namespace handler
