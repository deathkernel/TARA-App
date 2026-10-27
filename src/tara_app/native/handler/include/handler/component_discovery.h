#pragma once

#include <string>
#include <vector>

namespace handler {

struct Component {
    std::string name;
    std::string kind;
    std::string path;
    std::string version;
    bool executable{false};
};

std::vector<Component> discoverComponents(const std::vector<std::string>& names);
void printComponents(const std::vector<Component>& components);

} // namespace handler
