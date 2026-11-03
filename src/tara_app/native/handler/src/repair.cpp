#include "handler/repair.h"

#include "handler/action_engine.h"
#include "handler/history.h"
#include "handler/policy.h"
#include "handler/project_context.h"
#include "handler/transaction.h"
#include "handler/artifact_backup.h"
#include "handler/verification.h"
#include "handler/state_paths.h"

#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

namespace handler {

namespace {

bool validPackageName(const std::string& package) {
    if (package.empty() || package.size() > 128) return false;
    for (const unsigned char ch : package) {
        if (std::isalnum(ch) || ch == '-' || ch == '_' || ch == '.' ||
            ch == '[' || ch == ']')
            continue;
        return false;
    }
    return true;
}

std::filesystem::path repairStateRoot() {
    return handlerStateRoot();
}

std::filesystem::path pythonExecutableForCurrentContext() {
    // Do not trust VIRTUAL_ENV directly: it is caller-controlled environment
    // state and may point Handler at an arbitrary interpreter. Repair is
    // intentionally restricted to a project-local .venv/venv.
    const auto project = detectProjectContext(std::filesystem::current_path());
    if (!project.root.empty() && project.type == "Python") {
        for (const auto& name : {".venv", "venv"}) {
#ifdef _WIN32
            const auto candidate = project.root / name / "Scripts" / "python.exe";
#else
            const auto candidate = project.root / name / "bin" / "python";
#endif
            std::error_code ec;
            if (std::filesystem::is_regular_file(candidate, ec))
                return candidate;
        }
    }

    return {};
}

std::filesystem::path nodeWorkingDirectory() {
    const auto project = detectProjectContext(std::filesystem::current_path());
    if (!project.root.empty() && project.type == "Node.js")
        return project.root;
    return {};
}

std::string installedPythonPackageVersion(const std::filesystem::path& pythonPath,
                                          const std::string& package) {
    CommandSpec query{"python-repair-precheck", "python",
                      {"-m", "pip", "show", package, "--disable-pip-version-check"},
                      RiskLevel::Low, 30000};
    query.executablePath = pythonPath;
    const auto result = executeCommand(query);
    if (!result.started || result.exitCode != 0) return {};

    const std::string marker = "Version:";
    const auto pos = result.output.find(marker);
    if (pos == std::string::npos) return {};
    const auto begin = pos + marker.size();
    const auto end = result.output.find_first_of("\r\n", begin);
    std::string version = result.output.substr(
        begin, end == std::string::npos ? std::string::npos : end - begin);
    const auto first = version.find_first_not_of(" \t");
    const auto last = version.find_last_not_of(" \t");
    if (first == std::string::npos) return {};
    return version.substr(first, last - first + 1);
}

std::string installedNodePackageVersion(const std::filesystem::path& projectRoot,
                                        const std::string& package) {
    CommandSpec query{"node-repair-precheck", "npm",
                      {"ls", package, "--depth=0", "--json"},
                      RiskLevel::Low, 30000};
    query.workingDirectory = projectRoot;
    const auto result = executeCommand(query);
    if (!result.started || result.exitCode != 0) return {};

    const std::string dependencyKey = "\"" + package + "\"";
    const auto dependencyPos = result.output.find(dependencyKey);
    if (dependencyPos == std::string::npos) return {};

    const auto versionKey = result.output.find("\"version\"", dependencyPos + dependencyKey.size());
    if (versionKey == std::string::npos) return {};
    const auto colon = result.output.find(':', versionKey);
    if (colon == std::string::npos) return {};
    const auto begin = result.output.find('"', colon + 1);
    if (begin == std::string::npos) return {};
    const auto endQuote = result.output.find('"', begin + 1);
    if (endQuote == std::string::npos) return {};
    return result.output.substr(begin + 1, endQuote - begin - 1);
}

} // namespace

int repairPythonModule(const char* rawPackage) {
    const std::string package = rawPackage ? rawPackage : "";
    if (!validPackageName(package)) {
        std::cerr << "Repair blocked: invalid Python package name.\n";
        return 3;
    }

    const auto pythonPath = pythonExecutableForCurrentContext();
    if (pythonPath.empty()) {
        std::cerr << "Python repair blocked: project-local .venv/venv is required; global Python modification is blocked.\n";
        return 3;
    }
    const std::string target = pythonPath.string();
    std::cout << "Python repair requested for: " << package << "\n"
              << "Target interpreter: " << target << "\n";

    const std::string previousVersion = installedPythonPackageVersion(pythonPath, package);

    const auto policy = evaluatePolicy(SafetyMode::Confirm, RiskLevel::High);
    if (policy.requiresConfirmation) {
        std::cout << policy.reason << " [y/N]: ";
        std::string answer;
        std::getline(std::cin, answer);
        if (answer != "y" && answer != "Y") {
            std::cout << "Repair cancelled.\n";
            return kRepairCancelled;
        }
    }

    Transaction tx(SafetyMode::Confirm);
    const auto artifactRoot = repairStateRoot() / "transactions" / "artifacts";
    std::vector<ArtifactBackup> backups;
    for (const auto& file : {std::filesystem::path("requirements.txt"),
                             std::filesystem::path("pyproject.toml")}) {
        const auto backup = backupArtifact(file, artifactRoot / "python");
        if (!backup) {
            std::cerr << "Python repair blocked: transaction artifact backup failed for "
                      << file << ".\n";
            return 1;
        }
        backups.push_back(*backup);
    }
    const auto result = tx.runApproved(
        RiskLevel::High,
        [&] {
            CommandSpec install{"python-repair", "python",
                {"-m", "pip", "install", package, "--disable-pip-version-check", "--only-binary=:all:"},
                RiskLevel::High, 180000};
            install.executablePath = pythonPath;
            const auto r = executeCommand(install);
            std::cout << r.output;
            return r.started && r.exitCode == 0;
        },
        [&] {
            CommandSpec verify{"python-repair-verify", "python",
                {"-m", "pip", "show", package}, RiskLevel::Low, 30000};
            verify.executablePath = pythonPath;
            const auto r = executeCommand(verify);
            if (!r.started || r.exitCode != 0)
                return VerificationResult{false, "pip show", r.error};
            CommandSpec consistency{"python-repair-consistency", "python",
                {"-m", "pip", "check"}, RiskLevel::Low, 30000};
            consistency.executablePath = pythonPath;
            const auto check = executeCommand(consistency);
            return VerificationResult{check.started && check.exitCode == 0,
                                      "pip show + pip check",
                                      check.exitCode == 0 ? "" : check.error};
        },
        [&] {
            bool restored = true;
            for (const auto& backup : backups) restored = restoreArtifact(backup) && restored;
            if (!restored) return false;

            if (previousVersion.empty()) {
                CommandSpec rollback{"python-repair-rollback", "python",
                    {"-m", "pip", "uninstall", "-y", package,
                     "--disable-pip-version-check"}, RiskLevel::High, 120000};
                rollback.executablePath = pythonPath;
                const auto result = executeCommand(rollback);
                return result.started && result.exitCode == 0;
            }

            CommandSpec rollback{"python-repair-rollback", "python",
                {"-m", "pip", "install", package + "==" + previousVersion,
                 "--disable-pip-version-check", "--only-binary=:all:"}, RiskLevel::High, 120000};
            rollback.executablePath = pythonPath;
            const auto result = executeCommand(rollback);
            return result.started && result.exitCode == 0;
        });

    History history(repairStateRoot() / "history.log");
    if (!result.committed) {
        history.record("PYTHON_REPAIR_FAILED",
                       package + " | " + result.details +
                       " | snapshot=" + result.snapshotId);
        std::cerr << "Python repair did not commit: " << result.details << "\n";
        return 1;
    }

    std::cout << "Repair verified and committed: " << package << "\n";
    history.record("PYTHON_REPAIR_SUCCESS",
                   package + " | " + target + " | snapshot=" + result.snapshotId);
    return 0;
}

int repairNodeModule(const char* rawPackage) {
    const std::string package = rawPackage ? rawPackage : "";
    if (!validPackageName(package)) {
        std::cerr << "Repair blocked: invalid Node package name.\n";
        return 3;
    }

    const auto projectRoot = nodeWorkingDirectory();
    if (projectRoot.empty()) {
        std::cerr << "Node repair blocked: no package.json project detected.\n";
        return 3;
    }

    std::cout << "Node repair requested for: " << package << "\n"
              << "Target project: " << projectRoot << "\n";

    const std::string previousVersion = installedNodePackageVersion(projectRoot, package);

    const auto policy = evaluatePolicy(SafetyMode::Confirm, RiskLevel::High);
    if (policy.requiresConfirmation) {
        std::cout << policy.reason << " [y/N]: ";
        std::string answer;
        std::getline(std::cin, answer);
        if (answer != "y" && answer != "Y") {
            std::cout << "Repair cancelled.\n";
            return kRepairCancelled;
        }
    }

    Transaction tx(SafetyMode::Confirm);
    const auto artifactRoot = repairStateRoot() / "transactions" / "artifacts";
    std::vector<ArtifactBackup> backups;
    for (const auto& file : {projectRoot / "package.json", projectRoot / "package-lock.json"}) {
        const auto backup = backupArtifact(file, artifactRoot / "node");
        if (!backup) {
            std::cerr << "Node repair blocked: transaction artifact backup failed for "
                      << file << ".\n";
            return 1;
        }
        backups.push_back(*backup);
    }
    const auto result = tx.runApproved(
        RiskLevel::High,
        [&] {
            CommandSpec install{"node-repair", "npm",
                {"install", package, "--no-audit", "--no-fund", "--ignore-scripts"},
                RiskLevel::High, 180000};
            install.workingDirectory = projectRoot;
            const auto r = executeCommand(install);
            std::cout << r.output;
            return r.started && r.exitCode == 0;
        },
        [&] {
            CommandSpec verify{"node-repair-verify", "npm",
                {"ls", package, "--depth=0"}, RiskLevel::Low, 30000};
            verify.workingDirectory = projectRoot;
            const auto r = executeCommand(verify);
            return VerificationResult{r.started && r.exitCode == 0,
                                      "npm ls", r.error};
        },
        [&] {
            bool restored = true;
            for (const auto& backup : backups) restored = restoreArtifact(backup) && restored;
            if (!restored) return false;

            const bool hasLockfile = std::filesystem::is_regular_file(
                projectRoot / "package-lock.json");
            CommandSpec rollback{"node-repair-rollback", "npm",
                hasLockfile
                    ? std::vector<std::string>{"ci", "--ignore-scripts", "--no-audit", "--no-fund"}
                    : std::vector<std::string>{"install", "--ignore-scripts", "--no-audit", "--no-fund"},
                RiskLevel::High, 180000};
            rollback.workingDirectory = projectRoot;
            const auto result = executeCommand(rollback);
            if (!result.started || result.exitCode != 0) return false;
            return installedNodePackageVersion(projectRoot, package) == previousVersion;
        });

    History history(repairStateRoot() / "history.log");
    if (!result.committed) {
        history.record("NODE_REPAIR_FAILED",
                       package + " | " + result.details +
                       " | snapshot=" + result.snapshotId);
        std::cerr << "Node repair did not commit: " << result.details << "\n";
        return 1;
    }

    std::cout << "Repair verified and committed: " << package << "\n";
    history.record("NODE_REPAIR_SUCCESS",
                   package + " | " + projectRoot.string() +
                   " | snapshot=" + result.snapshotId);
    return 0;
}

} // namespace handler
