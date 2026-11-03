#include "handler/router.h"

#include <iostream>

namespace handler {

TaskRouter::TaskRouter(ModuleRegistry& registry) : registry_(registry) {}

int TaskRouter::dispatch(const std::string& command) const {
    if (command == "help" || command == "--help" || command == "-h") {
        std::cout << "Handler commands are routed through on-demand modules.\n";
        return registry_.run("help");
    }

    return registry_.run(command);
}

} // namespace handler
