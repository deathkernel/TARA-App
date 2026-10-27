#pragma once

#include <filesystem>
#include <string>

namespace handler {

struct EnvironmentState {
    std::string timestampUtc;
    std::string computerName;
    std::string userName;
    std::string tempPath;
    std::string pathValue;
    std::filesystem::path currentDirectory;
    std::string handlerVersion;
};

EnvironmentState captureEnvironmentState();
std::string formatState(const EnvironmentState& state);

} // namespace handler
