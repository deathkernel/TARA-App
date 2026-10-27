#include "handler/environment_guardian.h"
#include "handler/state_paths.h"
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#ifdef _WIN32
#include <windows.h>
#endif

namespace handler {
namespace {
std::string currentValue(const std::string& name) {
    const char* v = std::getenv(name.c_str());
    return v ? v : "";
}
bool present(const std::string& name) {
    const char* v = std::getenv(name.c_str());
    return v != nullptr;
}
bool trustedBaseline(const std::filesystem::path& file) {
    return isHandlerStatePath(file);
}
}
std::vector<VariableFinding> inspectEnvironmentVariables(const std::vector<std::string>& names) {
    std::vector<VariableFinding> out;
    for (const auto& name : names) {
        const bool exists = present(name);
        out.push_back({name, exists, exists ? "set" : "not set"});
    }
    return out;
}
bool isSensitiveVariable(const std::string& name) {
    std::string n = name;
    std::transform(n.begin(), n.end(), n.begin(),
                   [](unsigned char c){ return static_cast<char>(std::toupper(c)); });
    return n.find("KEY") != std::string::npos ||
           n.find("TOKEN") != std::string::npos ||
           n.find("SECRET") != std::string::npos ||
           n.find("PASSWORD") != std::string::npos ||
           n.find("PASSWD") != std::string::npos ||
           n.find("CREDENTIAL") != std::string::npos;
}
bool saveEnvironmentBaseline(const std::filesystem::path& file,
                             const std::vector<std::string>& names) {
    if (!trustedBaseline(file)) return false;
    std::error_code ec;
    std::filesystem::create_directories(file.parent_path(), ec);
    if (ec) return false;
    std::ofstream out(file);
    if (!out) return false;
    for (const auto& name : names) {
        if (isSensitiveVariable(name)) continue;
        out << name << "=" << currentValue(name) << "\n";
    }
    return out.good();
}
bool loadEnvironmentBaseline(const std::filesystem::path& file,
                             std::vector<EnvironmentEntry>& entries) {
    if (!trustedBaseline(file)) return false;
    std::ifstream in(file);
    if (!in) return false;
    entries.clear();
    std::string line;
    while (std::getline(in, line)) {
        const auto pos = line.find('=');
        if (pos == std::string::npos || pos == 0) continue;
        const auto name = line.substr(0, pos);
        if (isSensitiveVariable(name)) continue;
        entries.push_back({name, line.substr(pos + 1), EnvironmentScope::Process});
    }
    return !entries.empty();
}
EnvironmentDiff compareEnvironmentBaseline(const std::vector<EnvironmentEntry>& baseline) {
    EnvironmentDiff diff;
    for (const auto& e : baseline) {
        if (!present(e.name)) diff.missing.push_back(e.name);
        else if (currentValue(e.name) != e.value) diff.changed.push_back(e.name);
    }
    return diff;
}
bool restoreEnvironmentEntries(const std::vector<EnvironmentEntry>& entries,
                               EnvironmentScope scope, std::string& details) {
    if (scope == EnvironmentScope::System) {
        details = "system-scope environment restoration is blocked; use explicit administrator tooling";
        return false;
    }
    for (const auto& e : entries) {
        if (isSensitiveVariable(e.name)) continue;
#ifdef _WIN32
        if (!SetEnvironmentVariableA(e.name.c_str(), e.value.c_str())) {
            details = "failed to restore " + e.name;
            return false;
        }
        if (scope == EnvironmentScope::User) {
            HKEY key{};
            if (RegOpenKeyExA(HKEY_CURRENT_USER, "Environment", 0, KEY_SET_VALUE, &key) != ERROR_SUCCESS) {
                details = "current process restored; user environment registry could not be opened";
                return false;
            }
            const LONG rc = RegSetValueExA(key, e.name.c_str(), 0, REG_EXPAND_SZ,
                reinterpret_cast<const BYTE*>(e.value.c_str()),
                static_cast<DWORD>(e.value.size() + 1));
            RegCloseKey(key);
            if (rc != ERROR_SUCCESS) {
                details = "current process restored; persistent user value failed for " + e.name;
                return false;
            }
        }
#else
        if (setenv(e.name.c_str(), e.value.c_str(), 1) != 0) {
            details = "failed to restore " + e.name;
            return false;
        }
#endif
    }
    details = scope == EnvironmentScope::User
        ? "environment restored in process and persistent user scope"
        : "environment restored in current process";
    return true;
}
}
