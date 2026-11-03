#include "handler/environment_health.h"
#include <cstdlib>
#include <filesystem>
#include <iostream>
namespace handler {
std::vector<HealthFinding> inspectEnvironmentHealth() {
    std::vector<HealthFinding> out;
    const char* temp = std::getenv("TEMP");
    out.push_back({"TEMP", temp && *temp && std::filesystem::is_directory(temp), temp ? temp : "not set"});
    const char* path = std::getenv("PATH");
    out.push_back({"PATH", path && *path, path ? "available" : "not set"});
    std::error_code ec;
    const auto cwd = std::filesystem::current_path(ec);
    out.push_back({"WORKING_DIRECTORY", !ec && std::filesystem::is_directory(cwd), ec ? ec.message() : cwd.string()});
    return out;
}
void printEnvironmentHealth(const std::vector<HealthFinding>& findings) {
    for (const auto& f : findings)
        std::cout << "[" << (f.healthy ? "OK" : "WARN") << "] " << f.area << ": " << f.details << '\n';
}
}