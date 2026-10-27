#pragma once

#include <filesystem>
#include <string>
#include <vector>

namespace handler {

struct ProjectContext {
    std::filesystem::path root;
    std::string type;
    std::vector<std::string> manifests;
};

ProjectContext detectProjectContext(const std::filesystem::path& start);
void printProjectContext(const ProjectContext& context);

} // namespace handler
