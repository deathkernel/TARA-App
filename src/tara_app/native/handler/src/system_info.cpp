#include "handler/system_info.h"

#include <cstdlib>
#include <iostream>

namespace handler {

namespace {
std::string environmentValue(const char* name) {
    const char* value = std::getenv(name);
    return value ? std::string(value) : std::string{};
}

std::string firstEnvironmentValue(const char* first, const char* second) {
    const auto value = environmentValue(first);
    return value.empty() ? environmentValue(second) : value;
}
}

SystemHealth inspectSystem() {
    SystemHealth health;
#ifdef _WIN32
    health.computerName = environmentValue("COMPUTERNAME");
    health.userName = environmentValue("USERNAME");
    health.tempPath = firstEnvironmentValue("TEMP", "TMP");
#else
    health.computerName = firstEnvironmentValue("HOSTNAME", "HOST");
    health.userName = firstEnvironmentValue("USER", "LOGNAME");
    health.tempPath = firstEnvironmentValue("TMPDIR", "TMP");
    if (health.tempPath.empty()) health.tempPath = "/tmp";
#endif
    health.pathValue = environmentValue("PATH");
    health.pathAvailable = !health.pathValue.empty();
    health.tempAvailable = !health.tempPath.empty();
    return health;
}

void printSystemHealth(const SystemHealth& health) {
    std::cout << "Handler System Health\n";
    std::cout << "---------------------\n";
    std::cout << "Computer     : " << (health.computerName.empty() ? "<unknown>" : health.computerName) << '\n';
    std::cout << "User         : " << (health.userName.empty() ? "<unknown>" : health.userName) << '\n';
    std::cout << "TEMP         : " << (health.tempAvailable ? health.tempPath : "<missing>") << '\n';
    std::cout << "PATH         : " << (health.pathAvailable ? "available" : "missing") << '\n';
#ifdef _WIN32
    std::cout << "Scope        : PC / System\n";
#else
    std::cout << "Scope        : User / Development Environment\n";
#endif
}

} // namespace handler
