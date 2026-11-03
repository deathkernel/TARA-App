#pragma once
#include <string>
#include <vector>
namespace handler {
struct HealthFinding { std::string area; bool healthy{false}; std::string details; };
std::vector<HealthFinding> inspectEnvironmentHealth();
void printEnvironmentHealth(const std::vector<HealthFinding>& findings);
}