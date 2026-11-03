#include "handler/module.h"

#include <utility>

namespace handler {

void ModuleRegistry::registerModule(std::string name, ModuleTask task) {
    modules_.insert_or_assign(std::move(name), std::move(task));
}

int ModuleRegistry::run(const std::string& name) const {
    const auto it = modules_.find(name);
    if (it == modules_.end()) return 127;
    return it->second();
}

std::vector<std::string> ModuleRegistry::names() const {
    std::vector<std::string> result;
    result.reserve(modules_.size());
    for (const auto& [name, task] : modules_) result.push_back(name);
    return result;
}

} // namespace handler
