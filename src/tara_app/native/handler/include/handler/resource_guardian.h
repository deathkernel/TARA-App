#pragma once
#include <string>
#include <vector>
namespace handler {
struct PortFinding { int port{0}; bool available{true}; std::string details; };
std::vector<PortFinding> inspectPorts(const std::vector<int>& ports);
}