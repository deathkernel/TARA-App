#include "handler/decision_engine.h"

namespace handler {

std::vector<Decision> decideRepairs(const std::vector<DetectedError>& errors) {
    std::vector<Decision> decisions;
    for (const auto& error : errors) {
        if (error.category == "MISSING_COMMAND")
            decisions.push_back({"discover-component", RiskLevel::Low, "discover the missing command before changing the environment"});
        else if (error.category == "MISSING_MODULE")
            decisions.push_back({"inspect-dependencies", RiskLevel::Medium, "inspect the project manifest before installing anything"});
        else if (error.category == "DEPENDENCY_CONFLICT")
            decisions.push_back({"inspect-dependencies", RiskLevel::Medium, "inspect declared dependencies before proposing a change"});
        else if (error.category == "PERMISSION")
            decisions.push_back({"verify-permission-context", RiskLevel::High, "permission changes can alter system security"});
        else if (error.category == "RESOURCE_CONFLICT")
            decisions.push_back({"inspect-resource", RiskLevel::Medium, "resource ownership must be understood before stopping anything"});
    }
    return decisions;
}

} // namespace handler
