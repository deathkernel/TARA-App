#pragma once

#include <filesystem>
#include <string>

namespace handler {

class History {
public:
    explicit History(std::filesystem::path file);
    bool record(const std::string& event, const std::string& details = {}) const;

private:
    std::filesystem::path file_;
};

} // namespace handler
