#pragma once

#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

namespace handler {

using ModuleTask = std::function<int()>;

class ModuleRegistry {
public:
    void registerModule(std::string name, ModuleTask task);
    int run(const std::string& name) const;
    std::vector<std::string> names() const;

private:
    std::unordered_map<std::string, ModuleTask> modules_;
};

} // namespace handler
