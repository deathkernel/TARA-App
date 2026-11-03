#include "handler/toolchain_doctor.h"
#include "handler/action_engine.h"
#include "handler/component_discovery.h"
#include "handler/transaction.h"
#include "handler/verification.h"
#include <unordered_map>
#include <algorithm>
#include <cctype>

namespace handler {
namespace {
struct WingetTarget {
    const char* packageId;
    const char* executable;
};

const WingetTarget* wingetTarget(const std::string& tool) {
    static const std::unordered_map<std::string, WingetTarget> targets{
        {"python", {"Python.Python.3", "python"}},
        {"node", {"OpenJS.NodeJS", "node"}},
        {"git", {"Git.Git", "git"}},
        {"cmake", {"Kitware.CMake", "cmake"}},
        {"dotnet", {"Microsoft.DotNet.SDK", "dotnet"}}
    };
    const auto it = targets.find(tool);
    return it == targets.end() ? nullptr : &it->second;
}


std::string firstLine(const std::string& text) {
    const auto p = text.find_first_of("\r\n");
    return text.substr(0, p == std::string::npos ? text.size() : p);
}

#ifdef _WIN32
bool wingetAvailable() {
    CommandSpec spec{"winget-version", "winget", {"--version"}, RiskLevel::Low, 15000};
    const auto result = executeCommand(spec);
    return result.started && result.exitCode == 0;
}

bool verifyWingetSource(std::string& details) {
    CommandSpec spec{"winget-source", "winget",
                     {"source", "list"}, RiskLevel::Low, 30000};
    const auto result = executeCommand(spec);
    if (!result.started || result.exitCode != 0) {
        details = result.error.empty() ? "winget source query failed" : result.error;
        return false;
    }
    const auto output = result.output;
    if (output.find("winget") == std::string::npos) {
        details = "verified winget source was not reported by winget";
        return false;
    }
    return true;
}
#endif
}

std::vector<ToolchainFinding> inspectToolchain(const std::vector<std::string>& tools) {
    std::vector<ToolchainFinding> out;
    const auto discovered = discoverComponents(tools);
    std::unordered_map<std::string, Component> byName;
    for (const auto& component : discovered) byName[component.name] = component;

    for (const auto& name : tools) {
        const auto it = byName.find(name);
        if (it == byName.end()) {
            out.push_back({name, false, {}, {}, "MISSING", "not found"});
            continue;
        }
        CommandSpec spec{"toolchain-version", name, {"--version"}, RiskLevel::Low, 15000};
        if (name == "npm") spec.arguments = {"--version"};
        const auto result = executeCommand(spec);
        const std::string version = result.started && result.exitCode == 0
            ? firstLine(result.output) : "version unavailable";
        const bool healthy = result.started && result.exitCode == 0;
        out.push_back({name, true, it->second.path, version,
                       healthy ? "HEALTHY" : "DEGRADED",
                       healthy ? "version check passed" : "version command failed"});
    }
    return out;
}

std::vector<ToolchainRepair> proposeToolchainRepairs(
    const std::vector<ToolchainFinding>& findings) {
    std::vector<ToolchainRepair> out;
    for (const auto& f : findings) {
        const auto* target = wingetTarget(f.tool);
        if (f.status == "HEALTHY" && target) {
            out.push_back({f.tool, true,
                           std::string("winget upgrade --id ") + target->packageId + " --exact --source winget",
                           "installed tool can be upgraded through the verified winget source",
                           target->packageId});
            continue;
        }
        if (f.status == "DEGRADED" && target) {
            out.push_back({f.tool, true,
                           std::string("winget upgrade --id ") + target->packageId + " --exact --source winget",
                           "installed tool is unhealthy; in-place package repair is available",
                           target->packageId});
            continue;
        }
        if (f.status == "MISSING" && target) {
            out.push_back({f.tool, false, {},
                           "automatic installation of a missing runtime is blocked; explicit installation is required",
                           target->packageId});
            continue;
        }
        out.push_back({f.tool, false, {},
                       "automatic repair source is not defined", {}});
    }
    return out;
}

bool repairToolchain(const std::string& tool, std::string& details) {
#ifndef _WIN32
    (void)tool;
    details = "automatic toolchain repair is not enabled on this platform; inspect the toolchain and use an explicit package-manager action";
    return false;
#else
    const auto* target = wingetTarget(tool);
    if (!target) {
        details = "automatic repair source is not defined for " + tool;
        return false;
    }


    const auto finding = inspectToolchain({tool});
    if (finding.empty() || !finding.front().available) {
        details = "toolchain repair requires an already installed runtime; missing tools need explicit installation";
        return false;
    }
    if (!wingetAvailable()) {
        details = "winget is not available on PATH";
        return false;
    }
    if (!verifyWingetSource(details))
        return false;

    const std::string packageId = target->packageId;
    const std::string previousVersion =
        finding.front().version;
    if (previousVersion.empty() || previousVersion == "version unavailable") {
        details = "toolchain rollback is unsafe because the installed version could not be captured";
        return false;
    }

    Transaction tx(SafetyMode::Confirm);
    const auto result = tx.runApproved(
        RiskLevel::High,
        [&] {
            CommandSpec action{
                "toolchain-upgrade",
                "winget",
                {"upgrade", "--id", packageId, "--exact", "--source", "winget",
                 "--accept-source-agreements", "--accept-package-agreements", "--silent"},
                RiskLevel::High,
                600000
            };
            const auto r = executeCommand(action);
            details = r.output.empty() ? r.error : r.output;
            return r.started && r.exitCode == 0;
        },
        [&] {
            const auto findings = inspectToolchain({tool});
            const auto it = findings.empty() ? findings.end() : findings.begin();
            const bool ok = it != findings.end() && it->available &&
                            it->status == "HEALTHY";
            return VerificationResult{ok, "toolchain health check",
                                      ok ? it->version : "post-repair health check failed"};
        },
        [&] {
            CommandSpec rollback{
                "toolchain-rollback",
                "winget",
                {"install", "--id", packageId, "--exact", "--source", "winget",
                 "--version", previousVersion, "--force",
                 "--accept-source-agreements", "--accept-package-agreements", "--silent"},
                RiskLevel::High,
                600000
            };
            const auto r = executeCommand(rollback);
            if (!r.started || r.exitCode != 0) {
                details += " | rollback failed: exact previous version " + previousVersion +
                           " could not be restored";
                return false;
            }
            const auto restored = inspectToolchain({tool});
            const auto it = restored.empty() ? restored.end() : restored.begin();
            const bool ok = it != restored.end() && it->available &&
                            it->status == "HEALTHY" && it->version == previousVersion;
            details += ok
                ? " | rollback restored exact previous version " + previousVersion
                : " | rollback command succeeded but exact previous version verification failed";
            return ok;
        });
    if (!result.committed) {
        details += " | transaction=" + result.details +
                   " | snapshot=" + result.snapshotId;
        return false;
    }
    details = "verified toolchain upgrade committed | package=" + packageId +
              " | snapshot=" + result.snapshotId;
    return true;
#endif
}

} // namespace handler
