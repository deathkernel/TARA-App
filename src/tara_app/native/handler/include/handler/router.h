#pragma once

#include "handler/module.h"

#include <string>

namespace handler {

class TaskRouter {
public:
    explicit TaskRouter(ModuleRegistry& registry);
    int dispatch(const std::string& command) const;

private:
    ModuleRegistry& registry_;
};

} // namespace handler
