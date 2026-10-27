#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>

namespace handler {

struct CleanupResult {
    std::size_t filesRemoved{0};
    std::size_t directoriesRemoved{0};
    std::size_t skipped{0};
    std::uintmax_t bytesFreed{0};
    std::size_t candidates{0};
    std::uintmax_t candidateBytes{0};
    bool dryRun{false};
    std::size_t protectedSkipped{0};
    std::size_t recentSkipped{0};
    std::size_t lockedSkipped{0};
};

CleanupResult cleanTempDirectory(const std::filesystem::path& tempDirectory, bool dryRun = false);
void printCleanupResult(const CleanupResult& result);

} // namespace handler
