#pragma once

#include <string>

namespace handler {

struct SystemHealth {
    std::string computerName;
    std::string userName;
    std::string tempPath;
    std::string pathValue;
    bool pathAvailable{false};
    bool tempAvailable{false};
};

SystemHealth inspectSystem();

void printSystemHealth(const SystemHealth& health);

} // namespace handler
