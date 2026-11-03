#pragma once
#include <filesystem>
#include <string>
#include <vector>

namespace handler {
enum class EnvironmentScope { Process, User, System };

struct VariableFinding {
    std::string name;
    bool present{false};
    std::string details;
};

struct EnvironmentEntry {
    std::string name;
    std::string value;
    EnvironmentScope scope{EnvironmentScope::Process};
};

struct EnvironmentDiff {
    std::vector<std::string> missing;
    std::vector<std::string> changed;
    std::vector<std::string> extra;
};

std::vector<VariableFinding> inspectEnvironmentVariables(const std::vector<std::string>& names);
bool isSensitiveVariable(const std::string& name);
bool saveEnvironmentBaseline(const std::filesystem::path& file,
                             const std::vector<std::string>& names);
bool loadEnvironmentBaseline(const std::filesystem::path& file,
                             std::vector<EnvironmentEntry>& entries);
EnvironmentDiff compareEnvironmentBaseline(const std::vector<EnvironmentEntry>& baseline);
bool restoreEnvironmentEntries(const std::vector<EnvironmentEntry>& entries,
                               EnvironmentScope scope,
                               std::string& details);
}
