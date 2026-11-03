#pragma once
#include <string>
#include <vector>
namespace handler {
struct DependencyEdge { std::string source; std::string target; std::string relation; };
struct DependencyImpact {
    std::string dependency;
    std::vector<std::string> affected;
    std::string risk;
};
std::vector<DependencyEdge> buildDependencyGraph(const std::string& project,
                                                  const std::vector<std::string>& dependencies);
std::vector<DependencyEdge> buildTransitiveDependencyGraph(
    const std::vector<DependencyEdge>& directEdges,
    const std::vector<DependencyEdge>& transitiveEdges);
std::vector<DependencyImpact> analyzeDependencyImpact(
    const std::vector<DependencyEdge>& edges,
    const std::string& dependency);
void printDependencyGraph(const std::vector<DependencyEdge>& edges);
void printDependencyImpact(const std::vector<DependencyImpact>& impacts);
} // namespace handler
