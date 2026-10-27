#include "handler/environment_state.h"

#include <chrono>
#include <ctime>
#include <cstdlib>
#include <iomanip>
#include <sstream>

namespace handler {

namespace {

std::string env(const char* name) {
    const char* value = std::getenv(name);
    return value ? std::string(value) : std::string{};
}

std::string nowUtc() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t time = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#ifdef _WIN32
    gmtime_s(&tm, &time);
#else
    gmtime_r(&time, &tm);
#endif
    std::ostringstream out;
    out << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

} // namespace

EnvironmentState captureEnvironmentState() {
    EnvironmentState state;
    state.timestampUtc = nowUtc();
    state.computerName = env("COMPUTERNAME");
    state.userName = env("USERNAME");
    state.tempPath = env("TEMP");
#ifndef _WIN32
    if (state.computerName.empty()) state.computerName = env("HOSTNAME");
    if (state.userName.empty()) state.userName = env("USER");
    if (state.tempPath.empty()) state.tempPath = env("TMPDIR");
#endif
    state.pathValue = env("PATH");
    state.currentDirectory = std::filesystem::current_path();
    state.handlerVersion = "0.9.0";
    return state;
}

std::string formatState(const EnvironmentState& state) {
    std::ostringstream out;
    out << "timestamp_utc=" << state.timestampUtc << '\n'
        << "computer=" << state.computerName << '\n'
        << "user=" << state.userName << '\n'
        << "temp=" << state.tempPath << '\n'
        << "current_directory=" << state.currentDirectory.string() << '\n'
        << "handler_version=" << state.handlerVersion << '\n';
    return out.str();
}

} // namespace handler
