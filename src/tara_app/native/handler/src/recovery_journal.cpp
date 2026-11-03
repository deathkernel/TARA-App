#include "handler/recovery_journal.h"

#include <atomic>
#include <algorithm>
#include <chrono>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace handler {
namespace {

bool isActiveStage(const std::string& stage) {
    return stage == "START" || stage == "SNAPSHOT" ||
           stage == "SNAPSHOT_FAILED" || stage == "ACTION_BEGIN" ||
           stage == "VERIFY_BEGIN" || stage == "RECOVERY_REQUIRED";
}

bool isTerminalStage(const std::string& stage) {
    return stage == "COMMIT" || stage == "ROLLBACK" ||
           stage == "ABORT" || stage == "MANUAL_ROLLBACK" || stage == "RECOVERY_COMPLETE";
}

bool isKnownStage(const std::string& stage) {
    return isActiveStage(stage) || isTerminalStage(stage);
}

bool isValidTransactionId(const std::string& transactionId) {
    return !transactionId.empty() &&
           transactionId.find('|') == std::string::npos &&
           transactionId.find('\r') == std::string::npos &&
           transactionId.find('\n') == std::string::npos;
}

std::string sanitizeDetails(const std::string& details) {
    std::string sanitized;
    sanitized.reserve(details.size());
    for (const char ch : details) {
        if (ch == '\r') sanitized += "\\r";
        else if (ch == '\n') sanitized += "\\n";
        else sanitized += ch;
    }
    return sanitized;
}

std::string processIdString() {
#ifdef _WIN32
    return std::to_string(static_cast<unsigned long long>(GetCurrentProcessId()));
#else
    return std::to_string(static_cast<unsigned long long>(getpid()));
#endif
}

std::string nextCounter() {
    static std::atomic<unsigned long long> counter{0};
    return std::to_string(counter.fetch_add(1, std::memory_order_relaxed));
}

} // namespace

RecoveryJournal::RecoveryJournal(std::filesystem::path file) : file_(std::move(file)) {}

std::string RecoveryJournal::newTransactionId() {
    const auto now = std::chrono::system_clock::now().time_since_epoch().count();
    return std::to_string(static_cast<unsigned long long>(now)) +
           "-" + processIdString() + "-" + nextCounter();
}

bool RecoveryJournal::record(const std::string& stage, const std::string& details) const {
    if (!isKnownStage(stage)) return false;

    std::error_code ec;
    if (!file_.parent_path().empty())
        std::filesystem::create_directories(file_.parent_path(), ec);
    if (ec) return false;

    std::ofstream out(file_, std::ios::app);
    if (!out) return false;

    const auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    std::tm utc{};
#ifdef _WIN32
    gmtime_s(&utc, &now);
#else
    gmtime_r(&now, &utc);
#endif
    out << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ")
        << " | " << stage << " | " << sanitizeDetails(details) << '\n';
    out.flush();
    const bool writeSucceeded = out.good();
    out.close();
    return writeSucceeded && !out.fail();
}

bool RecoveryJournal::record(const std::string& transactionId,
                             const std::string& stage,
                             const std::string& details) const {
    if (!isValidTransactionId(transactionId) || !isKnownStage(stage)) return false;

    std::error_code ec;
    if (!file_.parent_path().empty())
        std::filesystem::create_directories(file_.parent_path(), ec);
    if (ec) return false;

    std::ofstream out(file_, std::ios::app);
    if (!out) return false;

    const auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    std::tm utc{};
#ifdef _WIN32
    gmtime_s(&utc, &now);
#else
    gmtime_r(&now, &utc);
#endif
    out << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ")
        << " | tx=" << transactionId
        << " | " << stage
        << " | " << sanitizeDetails(details) << '\n';
    out.flush();
    const bool writeSucceeded = out.good();
    out.close();
    return writeSucceeded && !out.fail();
}

std::vector<std::string> RecoveryJournal::unfinishedTransactionIds() const {
    std::ifstream in(file_);
    if (!in) return {};

    std::vector<std::string> activeIds;
    bool legacyActive = false;
    std::string line;
    while (std::getline(in, line)) {
        const auto first = line.find(" | ");
        if (first == std::string::npos) continue;
        const auto second = line.find(" | ", first + 3);
        if (second == std::string::npos) continue;

        const auto firstField = line.substr(first + 3, second - (first + 3));
        std::string transactionId;
        std::string stage;
        if (firstField.rfind("tx=", 0) == 0) {
            transactionId = firstField.substr(3);
            const auto third = line.find(" | ", second + 3);
            if (third == std::string::npos) continue;
            stage = line.substr(second + 3, third - (second + 3));
        } else {
            stage = firstField;
        }

        if (isActiveStage(stage)) {
            if (transactionId.empty()) {
                legacyActive = true;
            } else if (std::find(activeIds.begin(), activeIds.end(), transactionId) == activeIds.end()) {
                activeIds.push_back(transactionId);
            }
        } else if (isTerminalStage(stage)) {
            if (transactionId.empty()) {
                legacyActive = false;
            } else {
                activeIds.erase(
                    std::remove(activeIds.begin(), activeIds.end(), transactionId),
                    activeIds.end());
            }
        }
    }

    if (in.bad() && std::find(activeIds.begin(), activeIds.end(), std::string{}) == activeIds.end())
        activeIds.emplace_back();
    if (legacyActive)
        activeIds.emplace_back();
    return activeIds;
}

bool RecoveryJournal::hasCorruptEntries() const {
    std::error_code pathError;
    if (std::filesystem::is_directory(file_, pathError) || pathError)
        return true;

    std::ifstream in(file_);
    if (!in) {
        std::error_code ec;
        return std::filesystem::exists(file_, ec) || static_cast<bool>(ec);
    }

    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;

        const auto first = line.find(" | ");
        if (first == std::string::npos) return true;
        const auto second = line.find(" | ", first + 3);
        if (second == std::string::npos) return true;

        const auto firstField = line.substr(first + 3, second - (first + 3));
        if (firstField.rfind("tx=", 0) == 0) {
            if (firstField.size() <= 3) return true;
            const auto third = line.find(" | ", second + 3);
            if (third == std::string::npos) return true;
            const auto stage = line.substr(second + 3, third - (second + 3));
            if (stage.empty() || !isKnownStage(stage)) return true;
        } else {
            if (firstField.empty() || !isKnownStage(firstField)) return true;
        }
    }
    return in.bad();
}
bool RecoveryJournal::hasUnfinishedTransaction() const {
    return hasCorruptEntries() || !unfinishedTransactionIds().empty();
}

} // namespace handler
