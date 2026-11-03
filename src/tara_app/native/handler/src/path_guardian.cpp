#include "handler/path_guardian.h"
#include "handler/state_paths.h"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <unordered_set>
#ifdef _WIN32
#include <windows.h>
#endif

namespace handler {
namespace {
char separator() {
#ifdef _WIN32
    return ';';
#else
    return ':';
#endif
}
std::vector<std::string> currentEntries() {
    std::vector<std::string> out;
    const char* raw = std::getenv("PATH");
    if (!raw) return out;
    std::stringstream ss(raw);
    std::string item;
    while (std::getline(ss, item, separator()))
        if (!item.empty()) out.push_back(item);
    return out;
}
std::string join(const std::vector<std::string>& entries) {
    std::string result;
    for (const auto& e : entries) {
        if (!result.empty()) result += separator();
        result += e;
    }
    return result;
}
bool trustedBaseline(const std::filesystem::path& file) {
    return isHandlerStatePath(file);
}
}
std::vector<PathFinding> inspectPathEntries() {
    std::vector<PathFinding> out;
    for (const auto& entry : currentEntries()) {
        std::error_code ec;
        const bool exists = std::filesystem::is_directory(entry, ec);
        out.push_back({entry, exists, exists ? "directory exists" :
                       (ec ? ec.message() : "directory missing")});
    }
    return out;
}
PathRepairPlan analyzePathEntries() {
    PathRepairPlan plan;
    std::unordered_set<std::string> seen;
    for (const auto& entry : currentEntries()) {
        if (!seen.insert(entry).second) plan.duplicateEntries.push_back(entry);
        std::error_code ec;
        if (!std::filesystem::is_directory(entry, ec))
            plan.missingEntries.push_back(entry);
    }
    plan.details = "diagnostic only; no OS PATH changes were applied";
    return plan;
}
bool savePathBaseline(const std::filesystem::path& file) {
    if (!trustedBaseline(file)) return false;
    std::error_code ec;
    std::filesystem::create_directories(file.parent_path(), ec);
    if (ec) return false;
    std::ofstream out(file);
    if (!out) return false;
    for (const auto& entry : currentEntries()) out << entry << '\n';
    return out.good();
}
bool loadPathBaseline(const std::filesystem::path& file, std::vector<std::string>& entries) {
    if (!trustedBaseline(file)) return false;
    std::ifstream in(file);
    if (!in) return false;
    entries.clear();
    std::string line;
    while (std::getline(in, line))
        if (!line.empty()) entries.push_back(line);
    return true;
}
bool restorePathFromBaseline(const std::filesystem::path& file, std::string& details) {
    if (!trustedBaseline(file)) {
        details = "PATH baseline is outside Handler-owned state; refusing to trust it";
        return false;
    }
    std::vector<std::string> baseline;
    if (!loadPathBaseline(file, baseline)) {
        details = "PATH baseline could not be loaded";
        return false;
    }
    if (baseline.empty()) {
        details = "PATH baseline is empty; refusing restore";
        return false;
    }
    for (const auto& entry : baseline) {
        std::error_code ec;
        if (!std::filesystem::is_directory(entry, ec)) {
            details = "baseline contains missing directory: " + entry;
            return false;
        }
    }
    const std::string value = join(baseline);
#ifdef _WIN32
    if (!SetEnvironmentVariableA("PATH", value.c_str())) {
        details = "failed to update current process PATH";
        return false;
    }
    HKEY key{};
    if (RegOpenKeyExA(HKEY_CURRENT_USER, "Environment", 0, KEY_SET_VALUE, &key) != ERROR_SUCCESS) {
        details = "current PATH restored, persistent user PATH could not be opened";
        return false;
    }
    const LONG rc = RegSetValueExA(key, "Path", 0, REG_EXPAND_SZ,
                                   reinterpret_cast<const BYTE*>(value.c_str()),
                                   static_cast<DWORD>(value.size() + 1));
    RegCloseKey(key);
    if (rc != ERROR_SUCCESS) {
        details = "current PATH restored, persistent user PATH update failed";
        return false;
    }
    details = "current and persistent user PATH restored";
    return true;
#else
    if (setenv("PATH", value.c_str(), 1) != 0) {
        details = "failed to update current process PATH";
        return false;
    }
    details = "current process PATH restored; persistent shell configuration is unchanged";
    return true;
#endif
}
} // namespace handler
