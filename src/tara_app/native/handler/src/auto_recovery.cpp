#include "handler/auto_recovery.h"

#include "handler/error_detection.h"
#include "handler/project_context.h"
#include "handler/repair.h"

#include <filesystem>
#include <iostream>
#include <regex>
#include <string>

namespace handler {

namespace {

std::string extractPythonPackage(const std::string& text) {
    static const std::regex pattern(R"(no module named ['"]([^'"]+)['"])",
                                    std::regex::icase);
    std::smatch match;
    if (!std::regex_search(text, match, pattern) || match.size() < 2)
        return {};
    std::string package = match[1].str();
    const auto dot = package.find('.');
    if (dot != std::string::npos) package.resize(dot);
    return package;
}

std::string extractNodePackage(const std::string& text) {
    static const std::regex pattern(R"(cannot find module ['"]([^'"]+)['"])",
                                    std::regex::icase);
    std::smatch match;
    if (!std::regex_search(text, match, pattern) || match.size() < 2)
        return {};
    const std::string package = match[1].str();
    if (package.rfind("./", 0) == 0 || package.rfind("../", 0) == 0)
        return {};
    return package;
}

} // namespace

int autoRecover(const std::string& errorText) {
    if (detectErrors(errorText).empty()) {
        std::cerr << "Auto-recovery: no supported error pattern detected.\n";
        return 2;
    }

    const auto context = detectProjectContext(std::filesystem::current_path());
    if (context.root.empty()) {
        std::cerr << "Auto-recovery: no supported project context detected.\n";
        return 2;
    }

    if (context.type == "Python") {
        const auto package = extractPythonPackage(errorText);
        if (package.empty()) {
            std::cerr << "Auto-recovery: Python package could not be identified safely.\n";
            return 2;
        }
        std::cout << "Auto-recovery proposal: repair Python module '" << package
                  << "' in " << context.root << "\n";
        return repairPythonModule(package.c_str());
    }

    if (context.type == "Node.js") {
        const auto package = extractNodePackage(errorText);
        if (package.empty()) {
            std::cerr << "Auto-recovery: Node package could not be identified safely.\n";
            return 2;
        }
        std::cout << "Auto-recovery proposal: repair Node module '" << package
                  << "' in " << context.root << "\n";
        return repairNodeModule(package.c_str());
    }

    std::cerr << "Auto-recovery: ecosystem '" << context.type
              << "' has no automatic package repair yet.\n";
    return 2;
}

} // namespace handler
