#include "handler/dependency_graph.h"

#include <algorithm>
#include <iostream>
#include <set>
#include <unordered_map>

namespace handler {

std::vector<DependencyEdge> buildDependencyGraph(
    const std::string& project,
    const std::vector<std::string>& dependencies) {
    std::vector<DependencyEdge> graph;
    for (const auto& dependency : dependencies)
        graph.push_back({project, dependency, "declares"});
    return graph;
}

std::vector<DependencyEdge> buildTransitiveDependencyGraph(
    const std::vector<DependencyEdge>& directEdges,
    const std::vector<DependencyEdge>& transitiveEdges) {
    std::vector<DependencyEdge> out = directEdges;
    const auto addUnique = [&](const DependencyEdge& edge) {
        const auto it = std::find_if(out.begin(), out.end(),
            [&](const DependencyEdge& e) {
                return e.source == edge.source &&
                       e.target == edge.target &&
                       e.relation == edge.relation;
            });
        if (it == out.end()) out.push_back(edge);
    };

    for (const auto& edge : transitiveEdges) addUnique(edge);

    std::unordered_map<std::string, std::vector<std::string>> adjacency;
    for (const auto& edge : out) adjacency[edge.source].push_back(edge.target);

    for (const auto& root : directEdges) {
        std::vector<std::string> queue{root.target};
        std::set<std::string> visited{root.source};
        while (!queue.empty()) {
            const auto node = queue.back();
            queue.pop_back();
            if (!visited.insert(node).second) continue;

            if (node != root.target)
                addUnique({root.source, node, "transitive"});

            const auto it = adjacency.find(node);
            if (it != adjacency.end())
                for (const auto& next : it->second)
                    if (!visited.count(next)) queue.push_back(next);
        }
    }
    return out;
}

std::vector<DependencyImpact> analyzeDependencyImpact(
    const std::vector<DependencyEdge>& edges,
    const std::string& dependency) {
    std::set<std::string> affected;
    std::unordered_map<std::string, std::vector<std::string>> reverse;
    for (const auto& edge : edges) reverse[edge.target].push_back(edge.source);

    std::vector<std::string> queue{dependency};
    std::set<std::string> visited;
    while (!queue.empty()) {
        const auto node = queue.back();
        queue.pop_back();
        if (!visited.insert(node).second) continue;

        const auto it = reverse.find(node);
        if (it == reverse.end()) continue;
        for (const auto& parent : it->second) {
            if (parent != dependency) affected.insert(parent);
            if (!visited.count(parent)) queue.push_back(parent);
        }
    }

    DependencyImpact impact;
    impact.dependency = dependency;
    impact.affected.assign(affected.begin(), affected.end());
    impact.risk = impact.affected.size() > 1 ? "HIGH" :
                  impact.affected.size() == 1 ? "MEDIUM" : "LOW";
    return {impact};
}

void printDependencyGraph(const std::vector<DependencyEdge>& edges) {
    std::cout << "Dependency graph:\n";
    for (const auto& edge : edges)
        std::cout << "  " << edge.source << " --" << edge.relation
                  << "--> " << edge.target << '\n';
    if (edges.empty()) std::cout << "  No edges discovered.\n";
}

void printDependencyImpact(const std::vector<DependencyImpact>& impacts) {
    std::cout << "Dependency impact:\n";
    for (const auto& impact : impacts) {
        std::cout << "  " << impact.dependency << " | risk=" << impact.risk;
        if (impact.affected.empty()) std::cout << " | no dependents discovered";
        else {
            std::cout << " | affected: ";
            for (std::size_t i = 0; i < impact.affected.size(); ++i)
                std::cout << (i ? ", " : "") << impact.affected[i];
        }
        std::cout << "\n";
    }
}

} // namespace handler
