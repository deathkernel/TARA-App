#include "handler/project_context.h"

#include <iostream>

namespace handler {

ProjectContext detectProjectContext(const std::filesystem::path& start) {
    ProjectContext context;
    std::filesystem::path current = std::filesystem::absolute(start);

    for (int depth = 0; depth < 8 && !current.empty(); ++depth) {
        const auto has = [&](const char* name) {
            return std::filesystem::exists(current / name);
        };

        if (has("pyproject.toml") || has("requirements.txt") || has("Pipfile")) {
            context.root = current;
            context.type = "Python";
            if (has("pyproject.toml")) context.manifests.push_back("pyproject.toml");
            if (has("requirements.txt")) context.manifests.push_back("requirements.txt");
            if (has("Pipfile")) context.manifests.push_back("Pipfile");
            return context;
        }
        if (has("package.json")) {
            context.root = current;
            context.type = "Node.js";
            context.manifests.push_back("package.json");
            return context;
        }
        if (has("Cargo.toml")) {
            context.root = current;
            context.type = "Rust";
            context.manifests.push_back("Cargo.toml");
            return context;
        }
        if (has("go.mod")) {
            context.root = current;
            context.type = "Go";
            context.manifests.push_back("go.mod");
            return context;
        }
        if (has("CMakeLists.txt")) {
            context.root = current;
            context.type = "C/C++";
            context.manifests.push_back("CMakeLists.txt");
            return context;
        }

        const auto parent = current.parent_path();
        if (parent == current) break;
        current = parent;
    }
    return context;
}

void printProjectContext(const ProjectContext& context) {
    if (context.root.empty()) {
        std::cout << "Project context: not detected\n";
        return;
    }
    std::cout << "Project context:\n"
              << "  Type : " << context.type << '\n'
              << "  Root : " << context.root.string() << '\n'
              << "  Manifests:";
    for (const auto& manifest : context.manifests) std::cout << ' ' << manifest;
    std::cout << '\n';
}

} // namespace handler
