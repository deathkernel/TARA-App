#pragma once
#include <filesystem>
#include <string>
#include <vector>

namespace handler {
struct PathFinding { std::string entry; bool exists{false}; std::string details; };
struct PathRepairPlan {
    std::vector<std::string> missingEntries;
    std::vector<std::string> duplicateEntries;
    bool safe{true};
    std::string details;
};
std::vector<PathFinding> inspectPathEntries();
PathRepairPlan analyzePathEntries();
bool savePathBaseline(const std::filesystem::path& file);
bool loadPathBaseline(const std::filesystem::path& file, std::vector<std::string>& entries);
bool restorePathFromBaseline(const std::filesystem::path& file, std::string& details);
}
