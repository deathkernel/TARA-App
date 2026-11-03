#include "handler/recovery.h"

namespace handler {

RecoveryStrategy selectRecoveryStrategy(const std::vector<Decision>& decisions) {
    if (decisions.empty()) return {"no-op", 0, RiskLevel::Low, "no recovery action is indicated"};

    const auto& d = decisions.front();
    if (d.action == "discover-component") return {"discover-first", 100, d.risk, d.reason};
    if (d.action == "inspect-dependencies") return {"inspect-first", 95, d.risk, d.reason};
    if (d.action == "verify-permission-context") return {"permission-review", 80, d.risk, d.reason};
    if (d.action == "inspect-resource") return {"resource-review", 85, d.risk, d.reason};
    return {"no-op", 0, RiskLevel::Low, "unknown decision"};
}

bool recoveryAllowed(const RecoveryStrategy& strategy, SafetyMode mode) {
    return evaluatePolicy(mode, strategy.risk).allowed;
}

} // namespace handler
