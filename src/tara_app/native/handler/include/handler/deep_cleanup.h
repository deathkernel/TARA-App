#pragma once
#include <filesystem>
#include <cstdint>
namespace handler {
struct CleanupSummary { std::uintmax_t bytes{0}; std::uint64_t files{0}; std::uint64_t skipped{0}; };
CleanupSummary deepCleanup(const std::filesystem::path& root, bool backupFirst);
}