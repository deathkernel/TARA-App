#pragma once
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace handler {
struct DependencyInfo { std::string ecosystem; std::string manifest; std::vector<std::string> declared; };
struct DependencyRequirement { std::string name; std::string constraint; bool direct{true}; };
struct DependencyConflict { std::string name; std::string left; std::string right; std::string reason; };
struct DependencyCandidate { std::string name; std::string current; std::string constraint; std::string action; std::string reason; std::string selectedVersion; std::string command; };
struct DependencyVersion { int major{0}; int minor{0}; int patch{0}; std::string text; };

DependencyInfo inspectDependencies(const std::filesystem::path&, const std::string&);
std::vector<DependencyRequirement> parseDependencyRequirements(const DependencyInfo&);
std::vector<DependencyConflict> findDependencyConflicts(const std::vector<DependencyRequirement>&);
std::vector<DependencyCandidate> proposeDependencyUpgrades(const std::vector<DependencyRequirement>&);

std::optional<DependencyVersion> parseDependencyVersion(const std::string&);
bool satisfiesDependencyConstraint(const DependencyVersion&, const std::string&);
bool dependencyConstraintsCompatible(const std::vector<std::string>&);
std::optional<std::string> selectCompatibleDependencyVersion(const std::vector<std::string>&, const std::vector<std::string>&);

int upgradeDependency(const std::filesystem::path& projectRoot,
                      const std::string& ecosystem,
                      const std::string& package,
                      const std::string& constraint);

void printDependencies(const DependencyInfo&);
void printDependencyAnalysis(const std::vector<DependencyConflict>&, const std::vector<DependencyCandidate>&);
} // namespace handler
