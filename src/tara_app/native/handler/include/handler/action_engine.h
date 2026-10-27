#pragma once

#include "handler/command_engine.h"

#include <string>

namespace handler {

struct ActionResult {
    bool started{false};
    int exitCode{-1};
    std::string output;
    std::string error;
};

ActionResult executeCommand(const CommandSpec& command);

} // namespace handler
