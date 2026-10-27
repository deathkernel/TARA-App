#include "handler/uninstall.h"

#include "handler/action_engine.h"
#include "handler/artifact_backup.h"
#include "handler/dependency_manager.h"
#include "handler/transaction.h"
#include "handler/verification.h"
#include "handler/state_paths.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <regex>
#include <sstream>

namespace handler {
namespace {

bool validPackageName(const std::string& package) {
    if (package.empty() || package.size() > 214) return false;
    for (unsigned char c : package) {
        if (!(std::isalnum(c) || c == '-' || c == '_' || c == '.' ||
              c == '@' || c == '/')) return false;
    }
    return package.find('/') == std::string::npos ||
           package.rfind('@', 0) == 0;
}

std::filesystem::path pythonExecutable(const std::filesystem::path& root) {
    const auto venv = root / ".venv";
    const auto alt = root / "venv";
#ifdef _WIN32
    for (const auto& p : {venv / "Scripts" / "python.exe",
                          alt / "Scripts" / "python.exe"}) {
#else
    for (const auto& p : {venv / "bin" / "python",
                          alt / "bin" / "python"}) {
#endif
        std::error_code ec;
        if (std::filesystem::is_regular_file(p, ec)) return p;
    }
#ifdef _WIN32
    return "python.exe";
#else
    return "python";
#endif
}

bool hasProjectVirtualEnv(const std::filesystem::path& root) {
    std::error_code ec;
#ifdef _WIN32
    return std::filesystem::is_regular_file(root / ".venv" / "Scripts" / "python.exe", ec) ||
           std::filesystem::is_regular_file(root / "venv" / "Scripts" / "python.exe", ec);
#else
    return std::filesystem::is_regular_file(root / ".venv" / "bin" / "python", ec) ||
           std::filesystem::is_regular_file(root / "venv" / "bin" / "python", ec);
#endif
}

bool hasProjectNodeModules(const std::filesystem::path& root) {
    std::error_code ec;
    return std::filesystem::is_directory(root / "node_modules", ec);
}

std::string normalizePackage(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) {
                       return static_cast<char>(std::tolower(c));
                   });
    for (char& c : s)
        if (c == '_') c = '-';
    return s;
}

bool samePackage(const std::string& a, const std::string& b) {
    return normalizePackage(a) == normalizePackage(b);
}

std::string pythonVersion(const std::filesystem::path& root,
                          const std::string& package) {
    CommandSpec cmd{"uninstall-version", pythonExecutable(root).string(),
                    {"-m", "pip", "show", package, "--disable-pip-version-check"},
                    RiskLevel::Low, 30000, root};
    const auto result = executeCommand(cmd);
    if (!result.started || result.exitCode != 0) return {};
    std::istringstream lines(result.output);
    std::string line;
    while (std::getline(lines, line)) {
        if (line.rfind("Version:", 0) == 0)
            return line.substr(8).empty() ? std::string{} : line.substr(8).substr(
                line.substr(8).find_first_not_of(" \t"));
    }
    return {};
}

std::string nodeVersion(const std::filesystem::path& root,
                        const std::string& package) {
    CommandSpec cmd{"uninstall-version", "npm",
                    {"ls", package, "--depth=0", "--json"},
                    RiskLevel::Low, 30000, root};
    const auto result = executeCommand(cmd);
    if (!result.started || result.output.empty()) return {};

    // npm ls JSON contains the root project's version before the requested
    // dependency. Scope the search to the exact dependency entry.
    const std::string dependenciesKey = "\"dependencies\"";
    const auto dependenciesPos = result.output.find(dependenciesKey);
    if (dependenciesPos == std::string::npos) return {};
    const std::string packageKey = "\"" + package + "\"";
    const auto packagePos = result.output.find(packageKey, dependenciesPos + dependenciesKey.size());
    if (packagePos == std::string::npos) return {};
    const auto objectStart = result.output.find('{', packagePos + packageKey.size());
    const auto objectEnd = result.output.find('}', objectStart + 1);
    if (objectStart == std::string::npos || objectEnd == std::string::npos) return {};
    const std::string entry = result.output.substr(objectStart, objectEnd - objectStart + 1);
    const std::string versionKey = "\"version\"";
    const auto versionPos = entry.find(versionKey);
    if (versionPos == std::string::npos) return {};
    const auto colon = entry.find(':', versionPos + versionKey.size());
    const auto first = entry.find('"', colon + 1);
    const auto second = entry.find('"', first + 1);
    return (colon != std::string::npos && first != std::string::npos &&
            second != std::string::npos) ? entry.substr(first + 1, second - first - 1)
                                          : std::string{};
}

void appendDirectDependents(const std::filesystem::path& root,
                              const std::string& ecosystem,
                              const std::string& package,
                              std::vector<std::string>& affected) {
    const auto info = inspectDependencies(root, ecosystem);
    const auto requirements = parseDependencyRequirements(info);
    for (const auto& req : requirements) {
        if (samePackage(req.name, package)) continue;
        CommandSpec cmd{"uninstall-impact",
                        ecosystem == "Python" ? pythonExecutable(root).string() : "npm",
                        ecosystem == "Python"
                            ? std::vector<std::string>{"-m", "pip", "show", req.name}
                            : std::vector<std::string>{"ls", req.name, "--depth=0", "--json"},
                        RiskLevel::Low, 30000, root};
        const auto result = executeCommand(cmd);
        if (!result.started || result.exitCode != 0) continue;
        const auto normalized = normalizePackage(package);
        std::string output = normalizePackage(result.output);
        if (output.find("requires:") != std::string::npos &&
            output.find(normalized) != std::string::npos)
            affected.push_back(req.name + " (declared project dependency depends on target)");
    }
}

bool directDependency(const std::filesystem::path& root,
                      const std::string& ecosystem,
                      const std::string& package,
                      std::vector<std::string>& affected) {
    const auto info = inspectDependencies(root, ecosystem);
    const auto requirements = parseDependencyRequirements(info);
    bool found = false;
    for (const auto& req : requirements) {
        if (samePackage(req.name, package)) {
            found = true;
            affected.push_back(req.name + " (direct project dependency)");
        }
    }
    return found;
}

bool backupManifests(const UninstallPlan& plan,
                     const std::filesystem::path& root,
                     std::vector<ArtifactBackup>& backups) {
    backups.clear();
    const auto first = backupArtifact(plan.manifest, root);
    if (!first) return false;
    backups.push_back(*first);

    if (plan.ecosystem == UninstallEcosystem::NodeJs) {
        const auto lock = plan.projectRoot / "package-lock.json";
        if (std::filesystem::is_regular_file(lock)) {
            const auto b = backupArtifact(lock, root);
            if (!b) return false;
            backups.push_back(*b);
        }
    }
    return true;
}

bool installedAtVersion(const UninstallPlan& plan) {
    if (plan.ecosystem == UninstallEcosystem::Python)
        return pythonVersion(plan.projectRoot, plan.packageName) == plan.installedVersion;

    const auto version = nodeVersion(plan.projectRoot, plan.packageName);
    return version == plan.installedVersion;
}

bool reinstall(const UninstallPlan& plan) {
    if (plan.installedVersion.empty()) return false;
    if (plan.ecosystem == UninstallEcosystem::Python) {
        CommandSpec cmd{"uninstall-rollback", pythonExecutable(plan.projectRoot).string(),
                        {"-m", "pip", "install",
                         plan.packageName + "==" + plan.installedVersion,
                         "--disable-pip-version-check",
                         "--only-binary=:all:"},
                        RiskLevel::High, 120000, plan.projectRoot};
        const auto result = executeCommand(cmd);
        return result.started && result.exitCode == 0;
    }
    CommandSpec cmd{"uninstall-rollback", "npm",
                    {"install", plan.packageName + "@" + plan.installedVersion,
                     "--save-exact", "--no-audit", "--no-fund", "--ignore-scripts"},
                    RiskLevel::High, 120000, plan.projectRoot};
    const auto result = executeCommand(cmd);
    return result.started && result.exitCode == 0;
}

} // namespace

UninstallPlan planUninstall(const std::filesystem::path& projectRoot,
                            UninstallEcosystem ecosystem,
                            const std::string& package) {
    UninstallPlan plan;
    plan.projectRoot = projectRoot;
    plan.packageName = package;

    if (package.empty() || !validPackageName(package)) {
        plan.reason = "invalid package name";
        return plan;
    }

    std::error_code ec;
    const auto root = std::filesystem::weakly_canonical(projectRoot, ec);
    if (ec || !std::filesystem::is_directory(root, ec)) {
        plan.reason = "project root is not a directory";
        return plan;
    }
    plan.projectRoot = root;

    const std::string ecosystemName =
        ecosystem == UninstallEcosystem::Python ? "Python" : "Node.js";

    if (ecosystem == UninstallEcosystem::Python && !hasProjectVirtualEnv(root)) {
        plan.reason = "Python uninstall requires a project-local .venv or venv; global interpreter removal is blocked";
        return plan;
    }
    if (ecosystem == UninstallEcosystem::NodeJs && !hasProjectNodeModules(root)) {
        plan.reason = "Node.js uninstall requires project-local node_modules; global package removal is blocked";
        return plan;
    }
    const std::string manifestName =
        ecosystem == UninstallEcosystem::Python ? "requirements.txt" : "package.json";
    plan.manifest = root / manifestName;

    if (!std::filesystem::is_regular_file(plan.manifest, ec)) {
        plan.reason = "supported project manifest not found";
        return plan;
    }

    if (!directDependency(root, ecosystemName, package, plan.affected)) {
        plan.reason = "package is not a direct dependency of this project; transitive removal is blocked";
        return plan;
    }

    appendDirectDependents(root, ecosystemName, package, plan.affected);
    if (plan.affected.size() > 1) {
        plan.reason = "uninstall blocked: other declared project dependencies depend on this package";
        return plan;
    }

    plan.installedVersion = ecosystem == UninstallEcosystem::Python
        ? pythonVersion(root, package) : nodeVersion(root, package);
    if (plan.installedVersion.empty()) {
        plan.reason = "package is declared but not currently installed in the project environment";
        return plan;
    }

    if (ecosystem == UninstallEcosystem::Python) {
        const auto python = pythonExecutable(root);
        plan.command = python.string() + " -m pip uninstall -y " + package;
    } else {
        plan.command = "npm uninstall " + package;
    }

    plan.ecosystem = ecosystem;
    plan.allowed = true;
    plan.reason = "direct dependency found; exact installed version captured and rollback is available";
    return plan;
}

UninstallResult executeUninstall(const UninstallPlan& plan) {
    if (!plan.allowed)
        return {false, false, plan.reason, {}};

    std::vector<ArtifactBackup> backups;
    bool uninstallAttempted = false;

    Transaction tx(SafetyMode::Confirm);
    const auto result = tx.runApproved(
        RiskLevel::High,
        [&] {
            if (!backupManifests(plan, handlerTransactionRoot() / "uninstall-backups", backups))
                return false;

            uninstallAttempted = true;
            CommandSpec cmd{"package-uninstall",
                            plan.ecosystem == UninstallEcosystem::Python
                                ? pythonExecutable(plan.projectRoot).string() : "npm",
                            plan.ecosystem == UninstallEcosystem::Python
                                ? std::vector<std::string>{"-m", "pip", "uninstall", "-y", plan.packageName}
                                : std::vector<std::string>{"uninstall", plan.packageName},
                            RiskLevel::High, 120000, plan.projectRoot};
            const auto action = executeCommand(cmd);
            return action.started && action.exitCode == 0;
        },
        [&] {
            CommandSpec verify{"package-uninstall-verify",
                               plan.ecosystem == UninstallEcosystem::Python
                                   ? pythonExecutable(plan.projectRoot).string() : "npm",
                               plan.ecosystem == UninstallEcosystem::Python
                                   ? std::vector<std::string>{"-m", "pip", "show", plan.packageName}
                                   : std::vector<std::string>{"ls", plan.packageName, "--depth=0", "--json"},
                               RiskLevel::Low, 30000, plan.projectRoot};
            const auto check = executeCommand(verify);
            const bool absent = !check.started || check.exitCode != 0 ||
                (plan.ecosystem == UninstallEcosystem::NodeJs &&
                 check.output.find(plan.packageName) == std::string::npos);
            return VerificationResult{absent, "package absence verification",
                                      absent ? "package is absent" : "package is still installed"};
        },
        [&] {
            if (!uninstallAttempted) return true;

            bool restored = true;
            for (const auto& backup : backups)
                restored = restoreArtifact(backup) && restored;
            if (restored) restored = reinstall(plan);
            return restored;
        });

    if (!result.committed) {
        const bool rollbackVerified = result.rolledBack && installedAtVersion(plan);
        return {false, rollbackVerified,
                rollbackVerified ? "uninstall failed; exact package version was restored and verified"
                                 : "uninstall failed; rollback was attempted but could not be verified",
                result.snapshotId, rollbackVerified, result.rolledBack};
    }
    return {true, false, "package uninstalled and verified; recovery artifacts retained",
            result.snapshotId, false, false};
}

} // namespace handler
