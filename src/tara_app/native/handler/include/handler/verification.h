#pragma once

#include <string>

namespace handler {

struct VerificationResult {
    bool passed{false};
    std::string check;
    std::string details;
};

VerificationResult verifyFileExists(const std::string& path);
VerificationResult verifyDirectoryExists(const std::string& path);
void printVerification(const VerificationResult& result);

} // namespace handler
