#include "handler/policy.h"

namespace handler {

PolicyDecision evaluatePolicy(SafetyMode mode, RiskLevel risk) {
    if (mode == SafetyMode::Auto) {
        if (risk == RiskLevel::Low) return {true, false, "low-risk action allowed automatically"};
        return {false, true, "risk level requires explicit confirmation"};
    }

    if (mode == SafetyMode::Confirm) {
        if (risk == RiskLevel::Low) return {true, false, "low-risk action allowed"};
        return {false, true, "user confirmation required before execution"};
    }

    return {false, true, "strict mode requires explicit confirmation"};
}

std::string safetyModeName(SafetyMode mode) {
    switch (mode) {
    case SafetyMode::Auto: return "Auto";
    case SafetyMode::Confirm: return "Confirm";
    case SafetyMode::Strict: return "Strict";
    }
    return "Unknown";
}

} // namespace handler
