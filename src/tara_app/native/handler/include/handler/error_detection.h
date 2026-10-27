#pragma once

#include <string>
#include <vector>

namespace handler {

struct DetectedError {
    std::string category;
    std::string summary;
    std::string evidence;
    int confidence{0};
};

std::vector<DetectedError> detectErrors(const std::string& text);
void printDetectedErrors(const std::vector<DetectedError>& errors);

} // namespace handler
