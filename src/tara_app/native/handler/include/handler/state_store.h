#pragma once

#include "handler/environment_state.h"

#include <filesystem>
#include <optional>

namespace handler {

class StateStore {
public:
    explicit StateStore(std::filesystem::path root);

    bool saveCurrent(const EnvironmentState& state) const;
    std::optional<EnvironmentState> loadCurrent() const;
    std::filesystem::path root() const;

private:
    std::filesystem::path root_;
};

} // namespace handler
