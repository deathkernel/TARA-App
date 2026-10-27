#include "handler/risky_command.h"

#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

namespace handler {

CommandRiskResult inspectCommandRisk(const std::string& commandLine) {
    std::string s = commandLine;
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });

    if (s.find("format ") != std::string::npos ||
        s.find("diskpart") != std::string::npos ||
        s.find("reg delete") != std::string::npos)
        return {CommandRisk::Blocked, "command can cause destructive system changes"};

    if (s.find("del ") != std::string::npos ||
        s.find("rmdir ") != std::string::npos ||
        s.find("taskkill") != std::string::npos)
        return {CommandRisk::Review, "command can delete data or terminate processes"};

    if (s.find("setx ") != std::string::npos ||
        s.find("set ") != std::string::npos)
        return {CommandRisk::Review, "command can modify environment state"};

    if (s.find("winget uninstall") != std::string::npos)
        return {CommandRisk::Blocked, "toolchain removal is outside the automatic repair boundary"};

    if (s.find("pip uninstall") != std::string::npos ||
        s.find("npm uninstall") != std::string::npos)
        return {CommandRisk::Review, "package removal changes a project environment"};

    if (s.find("winget install") != std::string::npos ||
        s.find("winget upgrade") != std::string::npos)
        return {CommandRisk::Review, "package-manager operation can modify installed software"};

    return {CommandRisk::Safe, "no high-risk pattern detected"};
}

RiskLevel classifyCommandRisk(const std::string& executable,
                              const std::vector<std::string>& arguments) {
    std::string line = executable;
    for (const auto& arg : arguments) line += " " + arg;

    const auto pattern = inspectCommandRisk(line);
    if (pattern.risk == CommandRisk::Blocked) return RiskLevel::High;
    if (pattern.risk == CommandRisk::Review) return RiskLevel::High;

    const auto lower = [&] {
        std::string s = line;
        std::transform(s.begin(), s.end(), s.begin(),
                       [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
        return s;
    }();

    const bool versionQuery =
        lower.find("--version") != std::string::npos ||
        lower.find(" -v") != std::string::npos;

    const bool installOrUpdate =
        lower.find("pip install") != std::string::npos ||
        lower.find("npm install") != std::string::npos ||
        lower.find("git fetch") != std::string::npos ||
        lower.find("git pull") != std::string::npos ||
        lower.find("winget upgrade") != std::string::npos ||
        lower.find("winget install") != std::string::npos;

    if (versionQuery) return RiskLevel::Low;
    if (installOrUpdate) return RiskLevel::High;

    return RiskLevel::Medium;
}

} // namespace handler
