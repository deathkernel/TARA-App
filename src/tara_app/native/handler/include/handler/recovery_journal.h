#pragma once

#include <filesystem>
#include <string>
#include <vector>

namespace handler {

class RecoveryJournal {
public:
    explicit RecoveryJournal(std::filesystem::path file);
    bool record(const std::string& stage, const std::string& details) const;
    bool record(const std::string& transactionId, const std::string& stage,
                const std::string& details) const;
    static std::string newTransactionId();
    std::vector<std::string> unfinishedTransactionIds() const;
    bool hasCorruptEntries() const;
    bool hasUnfinishedTransaction() const;

private:
    std::filesystem::path file_;
};

} // namespace handler
