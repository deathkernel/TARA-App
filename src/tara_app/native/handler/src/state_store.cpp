#include "handler/state_store.h"

#include <fstream>
#include <utility>

namespace handler {

StateStore::StateStore(std::filesystem::path root) : root_(std::move(root)) {}

bool StateStore::saveCurrent(const EnvironmentState& state) const {
    std::error_code ec;
    std::filesystem::create_directories(root_, ec);
    if (ec) {
        return false;
    }

    std::ofstream out(root_ / "current.state", std::ios::trunc);
    if (!out) {
        return false;
    }

    out << formatState(state);
    return static_cast<bool>(out);
}

std::optional<EnvironmentState> StateStore::loadCurrent() const {
    std::ifstream in(root_ / "current.state");
    if (!in) {
        return std::nullopt;
    }

    EnvironmentState state;
    std::string line;
    while (std::getline(in, line)) {
        const auto separator = line.find('=');
        if (separator == std::string::npos) {
            continue;
        }
        const auto key = line.substr(0, separator);
        const auto value = line.substr(separator + 1);
        if (key == "timestamp_utc") state.timestampUtc = value;
        else if (key == "computer") state.computerName = value;
        else if (key == "user") state.userName = value;
        else if (key == "temp") state.tempPath = value;
        else if (key == "current_directory") state.currentDirectory = value;
        else if (key == "handler_version") state.handlerVersion = value;
    }

    return state;
}

std::filesystem::path StateStore::root() const {
    return root_;
}

} // namespace handler
