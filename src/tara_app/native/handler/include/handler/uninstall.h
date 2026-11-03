#pragma once
#include <filesystem>
#include <string>
#include <vector>

namespace handler {

enum class UninstallEcosystem { Python, NodeJs };

struct UninstallPlan {
    bool allowed{false};
    UninstallEcosystem ecosystem{UninstallEcosystem::Python};
    std::filesystem::path projectRoot;
    std::filesystem::path manifest;
    std::string packageName;
    std::string installedVersion;
    std::vector<std::string> affected;
    std::string command;
    std::string reason;
};

struct UninstallResult {
    bool success{false};
    bool rolledBack{false};
    std::string details;
    std::string snapshotId;
    bool rollbackVerified{false};
    bool rollbackAttempted{false};
};

UninstallPlan planUninstall(const std::filesystem::path& projectRoot,
                            UninstallEcosystem ecosystem,
                            const std::string& package);

UninstallResult executeUninstall(const UninstallPlan& plan);

} // namespace handler
