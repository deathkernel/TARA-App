#pragma once
#include <string>
#include <vector>
namespace handler {
struct UpdateCandidate {
    std::string tool;
    std::string currentPath;
    std::string currentVersion;
    std::string updateHint;
    bool actionable{false};
};
std::vector<UpdateCandidate> inspectToolUpdates(const std::vector<std::string>& tools);
}
