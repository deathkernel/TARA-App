#pragma once

#include "handler/error_detection.h"
#include "handler/command_engine.h"

#include <vector>

namespace handler {

struct Decision {
    std::string action;
    RiskLevel risk{RiskLevel::Low};
    std::string reason;
};

std::vector<Decision> decideRepairs(const std::vector<DetectedError>& errors);

} // namespace handler
