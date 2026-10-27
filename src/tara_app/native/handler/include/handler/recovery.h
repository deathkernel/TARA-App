#pragma once

#include "handler/decision_engine.h"

#include <string>
#include <vector>

namespace handler {

struct RecoveryStrategy {
    std::string name;
    int priority{0};
    RiskLevel risk{RiskLevel::Low};
    std::string reason;
};

RecoveryStrategy selectRecoveryStrategy(const std::vector<Decision>& decisions);
bool recoveryAllowed(const RecoveryStrategy& strategy, SafetyMode mode);

} // namespace handler
