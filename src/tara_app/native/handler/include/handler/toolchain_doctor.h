#pragma once
#include <string>
#include <vector>
namespace handler {
struct ToolchainFinding {
    std::string tool;
    bool available{false};
    std::string path;
    std::string version;
    std::string status;
    std::string details;
};
struct ToolchainRepair {
    std::string tool;
    bool supported{false};
    std::string command;
    std::string reason;
    std::string packageId;
};
std::vector<ToolchainFinding> inspectToolchain(const std::vector<std::string>& tools);
std::vector<ToolchainRepair> proposeToolchainRepairs(const std::vector<ToolchainFinding>& findings);
bool repairToolchain(const std::string& tool, std::string& details);
}
