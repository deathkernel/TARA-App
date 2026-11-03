#pragma once

#include "handler/environment_state.h"

#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace handler {

struct SnapshotInfo {
    std::string id;
    std::filesystem::path path;
};

class SnapshotStore {
public:
    explicit SnapshotStore(std::filesystem::path root);
    std::optional<SnapshotInfo> create(const EnvironmentState& state) const;
    std::optional<EnvironmentState> load(const SnapshotInfo& snapshot) const;
    std::vector<SnapshotInfo> list() const;
    std::optional<SnapshotInfo> find(const std::string& id) const;

private:
    std::filesystem::path root_;
};

} // namespace handler
