#include "handler/history.h"

#include <chrono>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <utility>

namespace handler {

namespace {

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

History::History(std::filesystem::path file) : file_(std::move(file)) {}

bool History::record(const std::string& event, const std::string& details) const {
    std::error_code ec;
    std::filesystem::create_directories(file_.parent_path(), ec);
    if (ec) return false;

    std::ofstream out(file_, std::ios::app);
    if (!out) return false;

    out << nowUtc() << " | " << event;
    if (!details.empty()) out << " | " << details;
    out << '\n';
    return static_cast<bool>(out);
}

} // namespace handler
