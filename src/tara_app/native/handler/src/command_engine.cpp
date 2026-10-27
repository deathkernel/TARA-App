#include "handler/command_engine.h"

#include <cctype>
#include <sstream>

namespace handler {

std::string quoteArgument(const std::string& value) {
    if (value.empty()) return "\"\"";

    bool needsQuotes = false;
    for (const char ch : value) {
        if (std::isspace(static_cast<unsigned char>(ch)) || ch == '\"' || ch == '\\') {
            needsQuotes = true;
            break;
        }
    }
    if (!needsQuotes) return value;

    std::string out;
    out.push_back('\"');
    std::size_t backslashes = 0;

    for (const char ch : value) {
        if (ch == '\\') {
            ++backslashes;
            continue;
        }
        if (ch == '\"') {
            out.append(backslashes * 2 + 1, '\\');
            out.push_back('\"');
            backslashes = 0;
            continue;
        }
        out.append(backslashes, '\\');
        backslashes = 0;
        out.push_back(ch);
    }

    out.append(backslashes * 2, '\\');
    out.push_back('\"');
    return out;
}

std::string buildCommandLine(const CommandSpec& command) {
    std::ostringstream out;
    out << quoteArgument(command.executable);
    for (const auto& arg : command.arguments)
        out << ' ' << quoteArgument(arg);
    return out.str();
}

bool isAllowedExecutable(const std::string& executable) {
    return executable == "where" || executable == "cmake"
        || executable == "git" || executable == "python"
        || executable == "python.exe" || executable == "node"
        || executable == "node.exe" || executable == "dotnet"
        || executable == "dotnet.exe" || executable == "npm"
        || executable == "npm.cmd" || executable == "winget"
        || executable == "winget.exe";
}

} // namespace handler
