#pragma once

#include <string>

namespace handler {

enum class SafetyMode { Auto, Confirm, Strict };
enum class RiskLevel { Low, Medium, High, Critical };

struct PolicyDecision {
    bool allowed{false};
    bool requiresConfirmation{false};
    std::string reason;
};

PolicyDecision evaluatePolicy(SafetyMode mode, RiskLevel risk);
std::string safetyModeName(SafetyMode mode);

} // namespace handler
