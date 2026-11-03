#pragma once
#include <string>
#include <vector>
#include "handler/policy.h"

namespace handler {
enum class CommandRisk { Safe, Review, Blocked };
struct CommandRiskResult { CommandRisk risk{CommandRisk::Safe}; std::string reason; };

CommandRiskResult inspectCommandRisk(const std::string& commandLine);
RiskLevel classifyCommandRisk(const std::string& executable, const std::vector<std::string>& arguments);
}
