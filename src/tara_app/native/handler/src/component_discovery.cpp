#include "handler/component_discovery.h"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <string>
#include <algorithm>
#include "handler/executable_trust.h"
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

namespace handler {

namespace {
std::string commandPath(const std::string& name) {
#ifdef _WIN32
    std::string candidate = name;
    if (candidate.find('.') == std::string::npos) candidate += ".exe";
    char buffer[MAX_PATH]{};
    const DWORD length = SearchPathA(nullptr, candidate.c_str(), nullptr, MAX_PATH, buffer, nullptr);
    if (!length) return {};
    return isTrustedExecutablePath(std::filesystem::path(std::string(buffer, length))) ? std::string(buffer, length) : std::string{};
#else
    const char* rawPath = std::getenv("PATH");
    if (!rawPath) return {};

    const std::string pathValue(rawPath);
    std::error_code currentEc;
    const auto currentRoot = std::filesystem::weakly_canonical(
        std::filesystem::current_path(), currentEc);
    std::size_t begin = 0;
    while (begin <= pathValue.size()) {
        const auto end = pathValue.find(':', begin);
        const auto entry = pathValue.substr(
            begin, end == std::string::npos ? std::string::npos : end - begin);
        if (!entry.empty()) {
            const auto candidate = std::filesystem::path(entry) / name;
            std::error_code ec;
            const auto canonical = std::filesystem::weakly_canonical(candidate, ec);
            if (!ec && std::filesystem::is_regular_file(canonical, ec) &&
                (ec.value() == 0)) {
                if (!currentEc && pathUnder(canonical, currentRoot))
                    return {};
                return canonical.string();
            }
        }
        if (end == std::string::npos) break;
        begin = end + 1;
    }
    return {};
#endif
}
}

std::vector<Component> discoverComponents(const std::vector<std::string>& names) {
    std::vector<Component> result;
    for (const auto& name : names) {
        const auto path = commandPath(name);
        if (!path.empty())
            result.push_back({name, "command", path, {}, true});
    }
    return result;
}

void printComponents(const std::vector<Component>& components) {
    if (components.empty()) {
        std::cout << "No requested components discovered.\n";
        return;
    }
    std::cout << "Discovered components:\n";
    for (const auto& component : components) {
        std::cout << "  " << component.name << " [" << component.kind << "] -> "
                  << component.path << '\n';
    }
}

} // namespace handler
