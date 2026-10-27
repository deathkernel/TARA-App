#include "handler/tool_updates.h"
#include "handler/risky_command.h"
#include "handler/safe_mode.h"
#include "handler/deep_cleanup.h"
#include "handler/uninstall.h"
#include "handler/environment_health.h"
#include "handler/path_guardian.h"
#include "handler/environment_guardian.h"
#include "handler/resource_guardian.h"
#include "handler/toolchain_doctor.h"
#include "handler/action_engine.h"
#include "handler/decision_engine.h"
#include "handler/recovery.h"
#include "handler/component_discovery.h"
#include "handler/dependency_graph.h"
#include "handler/dependency_manager.h"
#include "handler/environment_state.h"
#include "handler/error_detection.h"
#include "handler/history.h"
#include "handler/maintenance.h"
#include "handler/module.h"
#include "handler/project_context.h"
#include "handler/policy.h"
#include "handler/recovery_journal.h"
#include "handler/snapshot.h"
#include "handler/transaction.h"
#include "handler/transaction_lock.h"
#include "handler/verification.h"
#include "handler/router.h"
#include "handler/state_store.h"
#include "handler/system_info.h"
#include "handler/temp_cleaner.h"
#include "handler/repair.h"
#include "handler/auto_recovery.h"
#include "handler/state_paths.h"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {
constexpr const char* kVersion = "0.9.0";

std::filesystem::path stateRoot() {
    return handler::handlerStateRoot();
}

handler::History makeHistory() {
    return handler::History(stateRoot() / "history.log");
}

void printDecisions(const std::vector<handler::Decision>& decisions) {
    for (const auto& d : decisions)
        std::cout << d.action << " | risk=" << static_cast<int>(d.risk)
                  << " | " << d.reason << "\n";
}

int runUpdates() {
    for (const auto& u : handler::inspectToolUpdates(
             {"python", "node", "git", "cmake", "dotnet"})) {
        std::cout << u.tool << ": "
                  << (u.currentPath.empty() ? "missing" : u.currentPath)
                  << " | " << u.currentVersion
                  << " | " << u.updateHint << "\n";
    }
    return 0;
}

std::string joinArguments(int argc, char* argv[], int start) {
    std::string result;
    for (int i = start; i < argc; ++i) {
        if (!result.empty()) result += ' ';
        result += argv[i];
    }
    return result;
}

int runRisk(const std::string& line) {
    const auto r = handler::inspectCommandRisk(line);
    const char* label = r.risk == handler::CommandRisk::Safe ? "SAFE"
                      : r.risk == handler::CommandRisk::Review ? "REVIEW"
                      : "BLOCKED";
    std::cout << "Risk: " << label << " | " << r.reason << "\n";
    return r.risk == handler::CommandRisk::Blocked ? 3 : 0;
}

int runSafeMode() {
    const auto c = handler::createSafeModeContext(std::filesystem::current_path());
    std::cout << "Safe mode: " << (c.enabled ? "ready" : "failed")
              << "\nSandbox: " << c.root << "\n";
    return c.enabled ? 0 : 1;
}

handler::ProjectContext currentProject();
std::filesystem::path transactionRoot();
bool mutationBlockedByInterruptedTransaction();

int runUninstall(const std::string& ecosystemName, const std::string& package,
               bool dryRun) {
    handler::UninstallEcosystem ecosystem;
    if (ecosystemName == "python")
        ecosystem = handler::UninstallEcosystem::Python;
    else if (ecosystemName == "node")
        ecosystem = handler::UninstallEcosystem::NodeJs;
    else {
        std::cerr << "Usage: handler uninstall <python|node> <package> [--dry-run]\n";
        return 2;
    }

    const auto context = currentProject();
    if (context.root.empty()) {
        std::cerr << "Uninstall blocked: no supported project detected.\n";
        return 3;
    }

    const auto plan = handler::planUninstall(context.root, ecosystem, package);
    std::cout << "Uninstall plan\n--------------\n"
              << "Project : " << context.root << "\n"
              << "Package : " << package << "\n"
              << "Version : " << (plan.installedVersion.empty() ? "unknown" : plan.installedVersion) << "\n"
              << "Impact  : ";
    for (std::size_t i = 0; i < plan.affected.size(); ++i) {
        if (i) std::cout << ", ";
        std::cout << plan.affected[i];
    }
    std::cout << "\nReason  : " << plan.reason << "\n"
              << "Command : " << plan.command << "\n";

    if (!plan.allowed) {
        makeHistory().record("UNINSTALL_BLOCKED", package + " | " + plan.reason);
        return 3;
    }
    if (dryRun) {
        makeHistory().record("UNINSTALL_DRY_RUN", package + " | version=" + plan.installedVersion);
        std::cout << "Dry run: no package or project files were modified.\n";
        return 0;
    }

    if (mutationBlockedByInterruptedTransaction()) return 1;

    std::cout << "This will remove the package from the current project environment. "
                 "Handler will back up the manifest/lockfile and retain a recovery snapshot. [y/N]: ";
    std::string answer;
    std::getline(std::cin, answer);
    if (answer != "y" && answer != "Y") {
        makeHistory().record("UNINSTALL_CANCELLED", package);
        std::cout << "Uninstall cancelled.\n";
        return 2;
    }

    const auto result = handler::executeUninstall(plan);
    makeHistory().record(result.success ? "UNINSTALL_SUCCESS" : "UNINSTALL_FAILED",
                         package + " | version=" + plan.installedVersion +
                         " | snapshot=" + result.snapshotId);
    std::cout << result.details << "\n";
    if (result.rollbackAttempted)
        std::cout << "Rollback: "
                  << (result.rollbackVerified ? "verified" : "NOT VERIFIED") << "\n";
    return result.success ? 0 : 1;
}

int runToolchainRepair(const std::string& tool) {
    const auto findings = handler::inspectToolchain({tool});
    if (findings.empty() || !findings.front().available) {
        std::cerr << "Toolchain repair blocked: " << tool << " is not available. "
                  << "Missing runtimes require an explicit installer/source.\n";
        return 3;
    }
    std::cout << "Toolchain repair requested for " << tool
              << ". This may modify installed developer tooling. [y/N]: ";
    std::string answer;
    std::getline(std::cin, answer);
    if (answer != "y" && answer != "Y") {
        makeHistory().record("TOOLCHAIN_REPAIR_CANCELLED", tool);
        std::cout << "Toolchain repair cancelled.\n";
        return handler::kRepairCancelled;
    }
    std::string details;
    const bool ok = handler::repairToolchain(tool, details);
    std::cout << details << "\n";
    makeHistory().record(ok ? "TOOLCHAIN_REPAIR_SUCCESS" : "TOOLCHAIN_REPAIR_FAILED", tool);
    return ok ? 0 : 1;
}

int runDoctorRepair() {
    const auto findings = handler::inspectToolchain(
        {"python", "node", "git", "cmake", "dotnet", "java", "go", "cargo"});
    std::cout << "Toolchain Doctor\n================\n";
    for (const auto& f : findings)
        std::cout << "[" << f.status << "] " << f.tool
                  << " | " << (f.path.empty() ? "missing" : f.path)
                  << " | " << (f.version.empty() ? "no version" : f.version)
                  << " | " << f.details << "\n";
    const auto repairs = handler::proposeToolchainRepairs(findings);
    std::cout << "\nRepair candidates\n------------------\n";
    for (const auto& r : repairs)
        std::cout << "[" << (r.supported ? "SUPPORTED" : "REVIEW") << "] "
                  << r.tool << ": " << r.reason
                  << (r.command.empty() ? "" : " | " + r.command) << "\n";
    makeHistory().record("TOOLCHAIN_DOCTOR",
        "tools=" + std::to_string(findings.size()) +
        ", repair_candidates=" + std::to_string(repairs.size()));
    return 0;
}

int runDoctor() {
    std::cout << "Handler Doctor\n==============\n";
    const auto health = handler::inspectSystem();
    handler::printSystemHealth(health);

    std::cout << "\nToolchain:\n";
    for (const auto& tool : handler::inspectToolchain(
             {"python", "node", "git", "cmake", "dotnet", "java", "go", "cargo"})) {
        std::cout << "  [" << (tool.available ? "OK" : "MISSING") << "] "
                  << tool.tool << ": " << tool.details << "\n";
    }

    std::cout << "\nPorts:\n";
    for (const auto& port : handler::inspectPorts({3000, 5000, 8000, 8080})) {
        const bool probeUnavailable = port.details.find("probe unavailable") != std::string::npos;
        const char* status = probeUnavailable ? "UNKNOWN" : (port.available ? "FREE" : "BUSY");
        std::cout << "  [" << status << "] "
                  << port.port << ": " << port.details << "\n";
    }

    const auto context = currentProject();
    std::cout << "\nProject: "
              << (context.root.empty() ? "not detected" : context.root.string())
              << "\n";

    // The TARA-App diagnosis adapter is read-only: do not persist a Handler history entry.
    return 0;
}

int runEnvironmentBaseline(const std::string& file, const std::vector<std::string>& names) {
    if (names.empty()) return 2;
    if (!handler::saveEnvironmentBaseline(file, names)) {
        std::cerr << "Environment baseline could not be saved.\n";
        return 1;
    }
    std::cout << "Environment baseline saved: " << file << "\n";
    return 0;
}

int runEnvironmentAudit(const std::string& file) {
    std::vector<handler::EnvironmentEntry> entries;
    if (!handler::loadEnvironmentBaseline(file, entries)) {
        std::cerr << "Environment baseline could not be loaded.\n";
        return 2;
    }
    const auto diff = handler::compareEnvironmentBaseline(entries);
    std::cout << "Environment audit\n------------------\n"
              << "Missing : " << diff.missing.size() << "\n"
              << "Changed : " << diff.changed.size() << "\n";
    for (const auto& n : diff.missing) std::cout << "  [MISSING] " << n << "\n";
    for (const auto& n : diff.changed) std::cout << "  [CHANGED] " << n << "\n";
    makeHistory().record("ENVIRONMENT_AUDIT",
        "missing=" + std::to_string(diff.missing.size()) +
        ", changed=" + std::to_string(diff.changed.size()));
    return 0;
}

int runEnvironmentRepair(const std::string& file, bool userScope) {
    std::vector<handler::EnvironmentEntry> target;
    if (!handler::loadEnvironmentBaseline(file, target)) {
        std::cerr << "Environment repair blocked: invalid baseline.\n";
        return 2;
    }
    const auto rollbackFile = stateRoot() / "transactions" / "environment-rollback.baseline";
    std::vector<std::string> names;
    for (const auto& e : target) names.push_back(e.name);
    if (!handler::saveEnvironmentBaseline(rollbackFile, names)) {
        std::cerr << "Environment repair blocked: current baseline backup failed.\n";
        return 1;
    }
    std::cout << "Environment repair will restore " << target.size()
              << (userScope ? " variables in User scope" : " variables in Process scope")
              << ". [y/N]: ";
    std::string answer;
    std::getline(std::cin, answer);
    if (answer != "y" && answer != "Y") {
        makeHistory().record("ENVIRONMENT_REPAIR_CANCELLED");
        std::cout << "Environment repair cancelled.\n";
        return 0;
    }
    const auto scope = userScope ? handler::EnvironmentScope::User
                                 : handler::EnvironmentScope::Process;
    handler::Transaction tx(handler::SafetyMode::Confirm);
    const auto result = tx.runApproved(
        handler::RiskLevel::High,
        [&] {
            std::string details;
            const bool ok = handler::restoreEnvironmentEntries(target, scope, details);
            std::cout << details << "\n";
            return ok;
        },
        [&] {
            const auto diff = handler::compareEnvironmentBaseline(target);
            return handler::VerificationResult{
                diff.missing.empty() && diff.changed.empty(),
                "environment baseline comparison",
                (diff.missing.empty() && diff.changed.empty())
                    ? "baseline matches" : "baseline differs"};
        },
        [&] {
            std::vector<handler::EnvironmentEntry> rollback;
            if (!handler::loadEnvironmentBaseline(rollbackFile, rollback)) return false;
            std::string details;
            return handler::restoreEnvironmentEntries(rollback, scope, details);
        });
    if (!result.committed) {
        makeHistory().record("ENVIRONMENT_REPAIR_FAILED",
            result.details + " | snapshot=" + result.snapshotId);
        std::cerr << "Environment repair did not commit: " << result.details << "\n";
        return 1;
    }
    makeHistory().record("ENVIRONMENT_REPAIR_SUCCESS",
        file + " | snapshot=" + result.snapshotId);
    std::cout << "Environment repair verified and committed.\n";
    return 0;
}

int runPathRepair(const std::string& baselineFile) {
    std::filesystem::path baseline = baselineFile;
    if (!std::filesystem::exists(baseline)) {
        std::cerr << "PATH repair blocked: baseline not found: " << baseline << "\n";
        return 2;
    }
    std::vector<std::string> entries;
    if (!handler::loadPathBaseline(baseline, entries) || entries.empty()) {
        std::cerr << "PATH repair blocked: invalid or empty baseline.\n";
        return 2;
    }
    std::cout << "PATH repair will restore " << entries.size()
              << " baseline entries and may modify the persistent user PATH. [y/N]: ";
    std::string answer;
    std::getline(std::cin, answer);
    if (answer != "y" && answer != "Y") {
        std::cout << "PATH repair cancelled.\n";
        makeHistory().record("PATH_REPAIR_CANCELLED");
        return 0;
    }

    const auto rollbackFile = stateRoot() / "transactions" / "path-rollback.baseline";
    if (!handler::savePathBaseline(rollbackFile)) {
        std::cerr << "PATH repair blocked: current PATH could not be backed up.\n";
        return 1;
    }

    handler::Transaction tx(handler::SafetyMode::Confirm);
    const auto result = tx.runApproved(
        handler::RiskLevel::High,
        [&] {
            std::string details;
            const bool ok = handler::restorePathFromBaseline(baseline, details);
            std::cout << details << "\n";
            return ok;
        },
        [&] {
            const auto verifyFile = stateRoot() / "transactions" / "path-verify.baseline";
            const bool saved = handler::savePathBaseline(verifyFile);
            std::vector<std::string> actual;
            const bool loaded = saved && handler::loadPathBaseline(verifyFile, actual);
            std::error_code ec;
            std::filesystem::remove(verifyFile, ec);
            bool matches = loaded && actual == entries;
            return handler::VerificationResult{
                matches, "PATH baseline comparison",
                matches ? "current PATH matches trusted baseline"
                         : "current PATH differs from trusted baseline"};
        },
        [&] {
            std::string details;
            return handler::restorePathFromBaseline(rollbackFile, details);
        });

    if (!result.committed) {
        makeHistory().record("PATH_REPAIR_FAILED",
            result.details + " | snapshot=" + result.snapshotId);
        std::cerr << "PATH repair did not commit: " << result.details << "\n";
        return 1;
    }
    makeHistory().record("PATH_REPAIR_SUCCESS",
        "baseline=" + baseline.string() + " | snapshot=" + result.snapshotId);
    std::cout << "PATH repair verified and committed.\n";
    return 0;
}

int runPathAudit() {
    const auto plan = handler::analyzePathEntries();
    std::cout << "PATH audit\n----------\n"
              << "Missing entries : " << plan.missingEntries.size() << "\n"
              << "Duplicate entries: " << plan.duplicateEntries.size() << "\n"
              << "Mode: " << plan.details << "\n";
    for (const auto& e : plan.missingEntries) std::cout << "  [MISSING] " << e << "\n";
    for (const auto& e : plan.duplicateEntries) std::cout << "  [DUPLICATE] " << e << "\n";
    makeHistory().record("PATH_AUDIT",
        "missing=" + std::to_string(plan.missingEntries.size()) +
        ", duplicates=" + std::to_string(plan.duplicateEntries.size()));
    return 0;
}

int runProtection() {
    handler::printEnvironmentHealth(handler::inspectEnvironmentHealth());
    for (const auto& f : handler::inspectPathEntries())
        std::cout << "[" << (f.exists ? "OK" : "WARN") << "] PATH "
                  << f.entry << ": " << f.details << "\n";
    for (const auto& v : handler::inspectEnvironmentVariables(
             {"TEMP", "PATH", "USERPROFILE", "LOCALAPPDATA"}))
        std::cout << "[" << (v.present ? "OK" : "WARN") << "] ENV "
                  << v.name << ": " << v.details << "\n";
    for (const auto& p : handler::inspectPorts({3000, 5000, 8000, 8080}))
        std::cout << "[" << (p.available ? "OK" : "BUSY") << "] PORT "
                  << p.port << ": " << p.details << "\n";
    for (const auto& t : handler::inspectToolchain(
             {"python", "git", "node", "cmake", "dotnet"}))
        std::cout << "[" << (t.available ? "OK" : "WARN") << "] TOOL "
                  << t.tool << ": " << t.details << "\n";
    makeHistory().record("PROTECTION_CHECK",
        "environment/path/variables/ports/toolchain inspected");
    return 0;
}

int runDecide(const std::string& text) {
    const auto errors = handler::detectErrors(text);
    const auto decisions = handler::decideRepairs(errors);
    printDecisions(decisions);
    makeHistory().record("DECISION",
        "actions=" + std::to_string(decisions.size()));
    return decisions.empty() ? 0 : 1;
}

int runCommand(const std::string& executable,
               const std::vector<std::string>& args) {
    if (!handler::isAllowedExecutable(executable)) {
        std::cerr << "Command blocked: executable is not allowlisted.\n";
        return 3;
    }

    handler::CommandSpec spec{"cli-command", executable, args,
                              handler::classifyCommandRisk(executable, args)};
    std::cout << handler::buildCommandLine(spec) << "\n";

    const auto policy =
        handler::evaluatePolicy(handler::SafetyMode::Confirm, spec.risk);

    if (policy.requiresConfirmation) {
        std::cout << policy.reason << " [y/N]: ";
        std::string answer;
        std::getline(std::cin, answer);
        if (answer != "y" && answer != "Y") {
            std::cout << "Command cancelled.\n";
            return 0;
        }
    }
    if (!policy.allowed && !policy.requiresConfirmation) {
        std::cout << "Command blocked: " << policy.reason << "\n";
        return 3;
    }

    const auto result = handler::executeCommand(spec);
    std::cout << result.output;
    return result.started ? result.exitCode : 1;
}

void printUsage() {
    std::cout
        << "Handler - Developer Environment Guardian\n\n"
        << "Usage:\n"
        << "  handler health                 Inspect PC/system environment\n"
        << "  handler self-check             Run Handler's own checks\n"
        << "  handler temp-cleanup           Safely clean %TEMP%\n"
        << "  handler temp-cleanup --dry-run Preview TEMP cleanup\n"
        << "  handler maintenance            Run maintenance every 2 hours\n"
        << "  handler state                  Capture current environment state\n"
        << "  handler detect-error <text>    Detect known error patterns\n"
        << "  handler discover [tools...]    Discover tools on PATH\n"
        << "  handler project                Detect project context\n"
        << "  handler deps                   Inspect project dependencies\n"
        << "  handler graph                  Show dependency edges\n"
        << "  handler decide <error text>    Generate repair decisions\n"
        << "  handler command <tool> [...]   Execute an allowlisted command\n"
        << "  handler path-audit             Audit PATH without modifying the OS\n"
        << "  handler path-repair <baseline> Restore PATH from a trusted baseline\n"
        << "  handler env-baseline <file> <names...> Save safe environment baseline\n"
        << "  handler env-audit <file>      Compare environment with baseline\n"
        << "  handler env-repair <file> [--user] Restore environment safely\n"
        << "  handler protect                Run protection diagnostics\n"
        << "  handler doctor                 Run complete deterministic diagnostics\n"
        << "  handler doctor-repair          Diagnose toolchains and show guarded repair candidates\n"
        << "  handler toolchain-repair <tool> Repair a supported installed toolchain\n"
        << "  handler uninstall <python|node> <package> [--dry-run] Remove a direct project dependency safely\n"
        << "  handler updates                Inspect tool updates\n"
        << "  handler risk <command>         Inspect risky command patterns\n"
        << "  handler repair python-module <package> Repair a Python module safely\n"
        << "  handler repair node-module <package>   Repair a Node module in the detected project\n"
        << "  handler recover <error text>       Detect and propose a guarded repair\n"
        << "  handler safe-mode              Prepare isolated sandbox context\n"
        << "  handler modules                Show registered modules\n"
        << "  handler status                 Show saved environment status\n"
        << "  handler history                Show recent Handler events\n"
        << "  handler snapshots              List recovery snapshots\n"
        << "  handler rollback <id>          Restore Handler baseline from snapshot\n"
        << "  handler version                Show Handler version\n"
        << "  handler help                   Show this help\n";
}

handler::StateStore makeStateStore() {
    return handler::StateStore(stateRoot() / "state");
}

int runHealth() {
    const auto health = handler::inspectSystem();
    handler::printSystemHealth(health);
    const auto state = handler::captureEnvironmentState();
    if (!makeStateStore().saveCurrent(state))
        std::cerr << "[WARN] Could not persist environment state.\n";
    makeHistory().record("HEALTH_CHECK", "system observation completed");
    return 0;
}

int runSelfCheck() {
    const auto health = handler::inspectSystem();
    bool ok = true;
    std::cout << "Handler Self-Check\n------------------\n";

    if (health.tempAvailable)
        std::cout << "[OK] TEMP environment variable\n";
    else {
        std::cout << "[FAIL] TEMP environment variable\n";
        ok = false;
    }

    if (health.pathAvailable)
        std::cout << "[OK] PATH environment variable\n";
    else
        std::cout << "[WARN] PATH environment variable is missing\n";

    if (makeStateStore().saveCurrent(handler::captureEnvironmentState()))
        std::cout << "[OK] Environment state store\n";
    else {
        std::cout << "[FAIL] Environment state store\n";
        ok = false;
    }

    makeHistory().record("SELF_CHECK", ok ? "passed" : "failed");
    std::cout << (ok ? "\nSelf-check passed.\n"
                     : "\nSelf-check found a required problem.\n");
    return ok ? 0 : 1;
}

int runTempCleanup(bool dryRun = false) {
    const auto health = handler::inspectSystem();
    if (!health.tempAvailable) {
        std::cerr << "Handler: TEMP is not available. Cleanup skipped.\n";
        makeHistory().record("TEMP_CLEANUP_SKIPPED", "TEMP unavailable");
        return 1;
    }

    if (!dryRun) {
        const auto policy = handler::evaluatePolicy(
            handler::SafetyMode::Confirm, handler::RiskLevel::High);
        if (policy.requiresConfirmation) {
            std::cout << "TEMP cleanup will remove eligible entries older than 24 hours. [y/N]: ";
            std::string answer;
            std::getline(std::cin, answer);
            if (answer != "y" && answer != "Y") {
                std::cout << "TEMP cleanup cancelled.\n";
                makeHistory().record("TEMP_CLEANUP_CANCELLED");
                return 0;
            }
        }
    }

    std::cout << (dryRun ? "Previewing: " : "Cleaning: ")
              << health.tempPath << "\n";

    if (dryRun) {
        const auto result = handler::cleanTempDirectory(
            std::filesystem::path(health.tempPath), true);
        handler::printCleanupResult(result);
        makeHistory().record("TEMP_CLEANUP",
            "files=" + std::to_string(result.filesRemoved) +
            ", skipped=" + std::to_string(result.skipped) +
            ", dry_run=true");
        return 0;
    }

    if (mutationBlockedByInterruptedTransaction()) return 1;

    handler::TransactionLock cleanupLock(transactionRoot() / "transaction.lock");
    if (!cleanupLock.acquire()) {
        std::cerr << "TEMP cleanup blocked: another Handler transaction is active.\n";
        return 1;
    }

    handler::RecoveryJournal journal(transactionRoot() / "recovery.log");
    const auto transactionId = handler::RecoveryJournal::newTransactionId();
    if (!journal.record(transactionId, "START", "TEMP cleanup transaction started")) {
        std::cerr << "TEMP cleanup blocked: recovery journal unavailable.\n";
        return 1;
    }
    if (!journal.record(transactionId, "ACTION_BEGIN", "TEMP cleanup mutation started")) {
        std::cerr << "TEMP cleanup blocked: recovery journal could not record mutation start.\n";
        return 1;
    }

    const auto result = handler::cleanTempDirectory(
        std::filesystem::path(health.tempPath), false);
    handler::printCleanupResult(result);

    const bool completed = journal.record(
        transactionId,
        result.lockedSkipped == 0 ? "COMMIT" : "RECOVERY_REQUIRED",
        "TEMP cleanup completed; files=" + std::to_string(result.filesRemoved) +
            ", skipped=" + std::to_string(result.skipped));
    makeHistory().record("TEMP_CLEANUP",
        "files=" + std::to_string(result.filesRemoved) +
        ", skipped=" + std::to_string(result.skipped) +
        ", dry_run=false");

    if (!completed) {
        std::cerr << "TEMP cleanup completed, but recovery journal persistence failed; "
                     "review recovery state before further mutations.\n";
        return 1;
    }
    if (result.lockedSkipped != 0) {
        std::cerr << "TEMP cleanup completed partially; recovery review is required.\n";
        return 1;
    }
    return 0;
}

std::filesystem::path transactionRoot() {
    return stateRoot() / "transactions";
}

bool mutationBlockedByInterruptedTransaction() {
    handler::RecoveryJournal journal(transactionRoot() / "recovery.log");
    if (!journal.hasUnfinishedTransaction()) return false;
    std::cerr << "Operation blocked: an interrupted transaction requires recovery review. "
                 "Run 'handler history' and inspect the transaction journal before retrying.\n";
    return true;
}

int runSnapshots() {
    handler::SnapshotStore store(transactionRoot() / "snapshots");
    const auto snapshots = store.list();
    if (snapshots.empty()) {
        std::cout << "No recovery snapshots found.\n";
        return 0;
    }
    std::cout << "Recovery snapshots\n-------------------\n";
    for (const auto& snapshot : snapshots)
        std::cout << snapshot.id << " | " << snapshot.path.string() << '\n';
    return 0;
}

int runRollback(const std::string& id) {
    handler::SnapshotStore store(transactionRoot() / "snapshots");
    const auto snapshot = store.find(id);
    if (!snapshot) {
        std::cerr << "Rollback blocked: snapshot not found: " << id << "\n";
        return 2;
    }
    const auto state = store.load(*snapshot);
    if (!state) {
        std::cerr << "Rollback blocked: snapshot could not be read.\n";
        return 2;
    }

    std::cout << "Rollback target: " << snapshot->id << "\n"
              << "Captured: " << state->timestampUtc << "\n"
              << "Directory: " << state->currentDirectory.string() << "\n"
              << "Note: this restores Handler's saved baseline only; it does not "
                 "silently modify OS environment variables. [y/N]: ";
    std::string answer;
    std::getline(std::cin, answer);
    if (answer != "y" && answer != "Y") {
        std::cout << "Rollback cancelled.\n";
        makeHistory().record("ROLLBACK_CANCELLED", id);
        return 0;
    }

    handler::TransactionLock recoveryLock(transactionRoot() / "transaction.lock");
    if (!recoveryLock.acquire()) {
        std::cerr << "Rollback blocked: another Handler transaction is active.\n";
        return 1;
    }

    if (!makeStateStore().saveCurrent(*state)) {
        std::cerr << "Rollback failed: could not restore saved Handler state.\n";
        return 1;
    }
    handler::RecoveryJournal journal(transactionRoot() / "recovery.log");
    const auto unfinished = journal.unfinishedTransactionIds();
    if (unfinished.size() == 1 && !unfinished.front().empty()) {
        const auto& activeId = unfinished.front();
        if (!journal.record(activeId, "RECOVERY_REQUIRED",
                            "Handler baseline snapshot restored; underlying system rollback is not verified")) {
            std::cerr << "Handler baseline restored, but the recovery journal could not be updated; the transaction remains blocked.\n";
            return 1;
        }
        std::cerr << "Handler baseline restored, but transaction " << activeId
                  << " remains blocked: restoring Handler's saved state does not verify rollback of the underlying system change. "
                     "Complete recovery review before retrying mutations.\n";
        makeHistory().record("ROLLBACK_APPLIED_RECOVERY_REQUIRED",
                             id + " | transaction=" + activeId +
                             " | underlying system rollback not verified");
        return 1;
    }

    bool journalUpdated = false;
    if (unfinished.empty())
        journalUpdated = journal.record("MANUAL_ROLLBACK", id);
    else {
        std::cerr << "Rollback applied, but the recovery journal has a legacy or ambiguous active transaction state; "
                     "manual recovery review is required before further mutations.\n";
        return 1;
    }
    if (!journalUpdated) {
        std::cerr << "Rollback applied, but recovery journal could not be updated; retry recovery review before further mutations.\n";
        return 1;
    }
    makeHistory().record("ROLLBACK_APPLIED",
                         id + " | Handler baseline restored");
    std::cout << "Handler baseline restored from snapshot " << id << ".\n";
    return 0;
}

int runStatus() {
    const auto state = makeStateStore().loadCurrent();
    if (!state) {
        std::cout << "Handler status: no saved environment state. Run 'handler state'.\n";
        return 1;
    }
    std::cout << "Handler status\n---------------\n"
              << "Last capture : " << state->timestampUtc << "\n"
              << "Computer     : " << state->computerName << "\n"
              << "User         : " << state->userName << "\n"
              << "TEMP         : " << state->tempPath << "\n"
              << "Directory    : " << state->currentDirectory.string() << "\n"
              << "Version      : " << state->handlerVersion << "\n";
    return 0;
}

int runHistory() {
    const auto file = stateRoot() / "history.log";
    std::ifstream in(file);
    if (!in) {
        std::cout << "No Handler history found.\n";
        return 0;
    }
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(in, line)) lines.push_back(line);
    const std::size_t start = lines.size() > 20 ? lines.size() - 20 : 0;
    std::cout << "Handler history (latest " << lines.size() - start << ")\n"
              << "--------------------------------\n";
    for (std::size_t i = start; i < lines.size(); ++i)
        std::cout << lines[i] << '\n';
    return 0;
}

int runState() {
    const auto state = handler::captureEnvironmentState();
    std::cout << handler::formatState(state);
    if (!makeStateStore().saveCurrent(state)) {
        std::cerr << "Handler: failed to persist environment state.\n";
        return 1;
    }
    makeHistory().record("STATE_CAPTURED", "current environment state saved");
    return 0;
}

int runMaintenance() {
    handler::MaintenanceLoop loop(std::chrono::hours(2));
    std::cout << "Maintenance mode is non-interactive; destructive TEMP cleanup is skipped.\n";
    loop.run([] {
        runTempCleanup(true);
        runState();
    });
    return 0;
}

int runErrorDetect(const std::string& text) {
    const auto errors = handler::detectErrors(text);
    handler::printDetectedErrors(errors);
    makeHistory().record("ERROR_DETECTION",
        "patterns=" + std::to_string(errors.size()));
    return errors.empty() ? 0 : 1;
}

int runDiscover(const std::vector<std::string>& names) {
    const auto components = handler::discoverComponents(names);
    handler::printComponents(components);
    makeHistory().record("COMPONENT_DISCOVERY",
        "found=" + std::to_string(components.size()));
    return 0;
}

handler::ProjectContext currentProject() {
    return handler::detectProjectContext(std::filesystem::current_path());
}

int runProject() {
    const auto context = currentProject();
    handler::printProjectContext(context);
    makeHistory().record("PROJECT_CONTEXT",
        context.root.empty() ? "not detected" : context.root.string());
    return 0;
}

int runDeps(int argc, char* argv[]) {
    const auto context = currentProject();
    if (context.root.empty()) {
        std::cout << "No supported project detected in the current directory or its parents.\n";
        return 1;
    }
    const auto info = handler::inspectDependencies(context.root, context.type);
    handler::printDependencies(info);
    const auto requirements = handler::parseDependencyRequirements(info);
    const auto conflicts = handler::findDependencyConflicts(requirements);
    const auto candidates = handler::proposeDependencyUpgrades(requirements);
    handler::printDependencyAnalysis(conflicts, candidates);

    if (argc >= 4 && std::string(argv[2]) == "--upgrade") {
        const std::string package = argv[3];
        for (const auto& req : requirements) {
            if (req.name == package) {
                if (mutationBlockedByInterruptedTransaction()) return 1;
                return handler::upgradeDependency(context.root, context.type, req.name, req.constraint);
            }
        }
        std::cerr << "Dependency upgrade blocked: package is not declared by the current project.\n";
        return 3;
    }

    makeHistory().record("DEPENDENCY_INSPECTION", info.ecosystem);
    return conflicts.empty() ? 0 : 4;
}

int runGraph() {
    const auto context = currentProject();
    if (context.root.empty()) {
        std::cout << "No supported project detected.\n";
        return 1;
    }
    const auto info = handler::inspectDependencies(context.root, context.type);
    const auto edges =
        handler::buildDependencyGraph(context.root.filename().string(),
                                       info.declared);
    handler::printDependencyGraph(edges);
    for (const auto& dep : info.declared)
        handler::printDependencyImpact(
            handler::analyzeDependencyImpact(edges, dep));
    makeHistory().record("DEPENDENCY_GRAPH",
        "edges=" + std::to_string(edges.size()));
    return 0;
}

handler::ModuleRegistry buildModules() {
    handler::ModuleRegistry registry;
    registry.registerModule("help", [] { printUsage(); return 0; });
    registry.registerModule("health", runHealth);
    registry.registerModule("self-check", runSelfCheck);
    registry.registerModule("temp-cleanup", [] { return runTempCleanup(); });
    registry.registerModule("maintenance", runMaintenance);
    registry.registerModule("state", runState);
    registry.registerModule("status", runStatus);
    registry.registerModule("history", runHistory);
    registry.registerModule("version", [] {
        std::cout << "Handler " << kVersion << "\n";
        return 0;
    });
    registry.registerModule("modules", [] {
        std::cout << "Registered modules (activated on demand):\n"
                  << "  health\n  self-check\n  temp-cleanup\n"
                  << "  maintenance\n  state\n  status\n  history\n  version\n  modules\n";
        return 0;
    });
    return registry;
}

} // namespace

int main(int argc, char* argv[]) {
    auto registry = buildModules();
    handler::TaskRouter router(registry);

    if (argc < 2)
        return router.dispatch("help");

    const std::string command = argv[1];

    if (command == "path-audit") return runPathAudit();
    if (command == "env-baseline") {
        if (argc < 4) { std::cerr << "Usage: handler env-baseline <file> <name...>\\n"; return 2; }
        std::vector<std::string> names;
        for (int i = 3; i < argc; ++i) names.emplace_back(argv[i]);
        return runEnvironmentBaseline(argv[2], names);
    }
    if (command == "env-audit") {
        if (argc < 3) { std::cerr << "Usage: handler env-audit <file>\\n"; return 2; }
        return runEnvironmentAudit(argv[2]);
    }
    if (command == "env-repair") {
        if (mutationBlockedByInterruptedTransaction()) return 1;
        if (argc < 3) { std::cerr << "Usage: handler env-repair <file> [--user]\\n"; return 2; }
        return runEnvironmentRepair(argv[2], argc >= 4 && std::string(argv[3]) == "--user");
    }
    if (command == "path-repair") {
        if (mutationBlockedByInterruptedTransaction()) return 1;
        if (argc < 3) { std::cerr << "Usage: handler path-repair <baseline-file>\\n"; return 2; }
        return runPathRepair(argv[2]);
    }
    if (command == "protect") return runProtection();
    if (command == "uninstall") {
        if (mutationBlockedByInterruptedTransaction()) return 1;
        if (argc < 4) {
            std::cerr << "Usage: handler uninstall <python|node> <package> [--dry-run]\n";
            return 2;
        }
        return runUninstall(argv[2], argv[3], argc >= 5 && std::string(argv[4]) == "--dry-run");
    }
    if (command == "toolchain-repair") {
        if (mutationBlockedByInterruptedTransaction()) return 1;
        if (argc < 3) { std::cerr << "Usage: handler toolchain-repair <tool>\\n"; return 2; }
        return runToolchainRepair(argv[2]);
    }
    if (command == "doctor-repair") {
        if (mutationBlockedByInterruptedTransaction()) return 1;
        return runDoctorRepair();
    }
    if (command == "doctor") return runDoctor();
    if (command == "updates") return runUpdates();
    if (command == "risk") {
        if (argc < 3) return 2;
        return runRisk(joinArguments(argc, argv, 2));
    }
    if (command == "safe-mode") return runSafeMode();
    if (command == "snapshots") return runSnapshots();
    if (command == "rollback") {
        if (argc < 3) { std::cerr << "Usage: handler rollback <snapshot-id>\n"; return 2; }
        return runRollback(argv[2]);
    }

    if (command == "recover") {
        if (argc < 3) {
            std::cerr << "Usage: handler recover <error text>\n";
            return 2;
        }
        if (mutationBlockedByInterruptedTransaction()) return 1;
        return handler::autoRecover(joinArguments(argc, argv, 2));
    }

    if (command == "repair") {
        if (argc < 4) {
            std::cerr << "Usage: handler repair <python-module|node-module> <package>\n";
            return 2;
        }
        const std::string target = argv[2];
        if (target != "python-module" && target != "node-module") {
            std::cerr << "Unknown repair target: " << target << "\n";
            return 2;
        }
        if (mutationBlockedByInterruptedTransaction()) return 1;
        if (target == "python-module")
            return handler::repairPythonModule(argv[3]);
        return handler::repairNodeModule(argv[3]);
    }

        if (command == "temp-cleanup" && argc >= 3 &&
        std::string(argv[2]) == "--dry-run")
        return runTempCleanup(true);

    if (command == "decide") {
        if (argc < 3) {
            std::cerr << "Usage: handler decide <error text>\n";
            return 2;
        }
        return runDecide(joinArguments(argc, argv, 2));
    }

    if (command == "command") {
        if (argc < 3) {
            std::cerr << "Usage: handler command <tool> [args...]\n";
            return 2;
        }
        std::vector<std::string> args;
        for (int i = 3; i < argc; ++i)
            args.emplace_back(argv[i]);
        return runCommand(argv[2], args);
    }

    if (command == "detect-error") {
        if (argc < 3) {
            std::cerr << "Usage: handler detect-error <error text>\n";
            return 2;
        }
        return runErrorDetect(joinArguments(argc, argv, 2));
    }

    if (command == "discover") {
        std::vector<std::string> names;
        for (int i = 2; i < argc; ++i)
            names.emplace_back(argv[i]);
        if (names.empty())
            names = {"python", "node", "git", "cmake", "dotnet",
                     "java", "go", "cargo"};
        return runDiscover(names);
    }

    if (command == "project") return runProject();
    if (command == "deps") return runDeps(argc, argv);
    if (command == "dependency-upgrade") {
        if (argc < 3) { std::cerr << "Usage: handler dependency-upgrade <package>\n"; return 2; }
        const auto context = currentProject();
        if (context.root.empty()) { std::cerr << "No supported project detected.\n"; return 1; }
        const auto info = handler::inspectDependencies(context.root, context.type);
        const auto requirements = handler::parseDependencyRequirements(info);
        for (const auto& req : requirements)
            if (req.name == argv[2]) {
                if (mutationBlockedByInterruptedTransaction()) return 1;
                return handler::upgradeDependency(context.root, context.type, req.name, req.constraint);
            }
        std::cerr << "Dependency upgrade blocked: package is not declared by the current project.\n";
        return 3;
    }
        if (command == "graph") return runGraph();

    const int result = router.dispatch(command);
    if (result == 127) {
        std::cerr << "Unknown Handler command: " << command << "\n\n";
        printUsage();
        return 2;
    }
    return result;
}
