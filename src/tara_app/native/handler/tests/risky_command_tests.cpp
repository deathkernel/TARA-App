#include "handler/risky_command.h"

#include <iostream>
#include <string>
#include <vector>

namespace {

int failures = 0;

void expectRisk(const std::string& label,
                const std::string& executable,
                const std::vector<std::string>& arguments,
                handler::RiskLevel expected) {
    const auto actual = handler::classifyCommandRisk(executable, arguments);
    if (actual == expected) {
        std::cout << "[PASS] " << label << "\n";
        return;
    }

    std::cerr << "[FAIL] " << label
              << " | expected=" << static_cast<int>(expected)
              << " actual=" << static_cast<int>(actual) << "\n";
    ++failures;
}

} // namespace

int main() {
    using handler::RiskLevel;

    expectRisk("pip install with verbose flag remains high risk",
               "python", {"-m", "pip", "install", "sample", "-v"},
               RiskLevel::High);
    expectRisk("pip install with explicit version remains high risk",
               "python", {"-m", "pip", "install", "sample", "--version", "1.2.3"},
               RiskLevel::High);
    expectRisk("npm install with verbose flag remains high risk",
               "npm", {"install", "sample", "--verbose"},
               RiskLevel::High);
    expectRisk("git pull with short verbose flag remains high risk",
               "git", {"pull", "-v"},
               RiskLevel::High);
    expectRisk("git fetch remains high risk",
               "git", {"fetch", "origin"},
               RiskLevel::High);
    expectRisk("pip uninstall remains high risk",
               "python", {"-m", "pip", "uninstall", "sample", "-y"},
               RiskLevel::High);
    expectRisk("winget uninstall remains high risk",
               "winget", {"uninstall", "sample"},
               RiskLevel::High);

    expectRisk("python version query is low risk",
               "python", {"--version"}, RiskLevel::Low);
    expectRisk("npm version query is low risk",
               "npm", {"--version"}, RiskLevel::Low);
    expectRisk("read-only pip list remains medium risk",
               "python", {"-m", "pip", "list"}, RiskLevel::Medium);

    return failures == 0 ? 0 : 1;
}
