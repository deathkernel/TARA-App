#include "handler/temp_cleaner.h"

#include <chrono>
#include <iostream>

namespace handler {

namespace {
bool protectedEntry(const std::filesystem::path& path,
                    const std::filesystem::path& tempDirectory) {
    std::error_code ec;
    const auto canonicalTemp = std::filesystem::weakly_canonical(tempDirectory, ec);
    ec.clear();
    const auto canonicalEntry = std::filesystem::weakly_canonical(path, ec);
    if (ec || canonicalTemp.empty() || canonicalEntry.empty()) return true;
    if (canonicalEntry == canonicalTemp) return true;
    // Never remove a Handler state directory if TEMP was configured unusually.
    const auto name = canonicalEntry.filename().string();
    return name == ".handler" || name == "Handler";
}

bool recentlyModified(const std::filesystem::path& path) {
    std::error_code ec;
    const auto modified = std::filesystem::last_write_time(path, ec);
    if (ec) return true;
    const auto now = std::filesystem::file_time_type::clock::now();
    return now - modified < std::chrono::hours(24);
}
} // namespace

CleanupResult cleanTempDirectory(const std::filesystem::path& tempDirectory, bool dryRun) {
    CleanupResult result;
    result.dryRun = dryRun;

    std::error_code ec;
    if (tempDirectory.empty() || !std::filesystem::exists(tempDirectory, ec) ||
        !std::filesystem::is_directory(tempDirectory, ec)) return result;

    const auto canonicalTemp = std::filesystem::weakly_canonical(tempDirectory, ec);
    if (ec || canonicalTemp.empty() || canonicalTemp == canonicalTemp.root_path())
        return result;

    for (const auto& entry : std::filesystem::directory_iterator(
             tempDirectory, std::filesystem::directory_options::skip_permission_denied, ec)) {
        if (ec) {
            ++result.skipped;
            ec.clear();
            continue;
        }

        if (protectedEntry(entry.path(), tempDirectory)) {
            ++result.skipped;
            ++result.protectedSkipped;
            continue;
        }

        if (recentlyModified(entry.path())) {
            ++result.skipped;
            ++result.recentSkipped;
            continue;
        }

        std::uintmax_t size = 0;
        std::error_code sizeError;
        if (entry.is_regular_file(sizeError) && !sizeError) {
            size = entry.file_size(sizeError);
            if (sizeError) size = 0;
        }

        ++result.candidates;
        result.candidateBytes += size;
        if (dryRun) continue;

        std::error_code removeError;
        const auto removedCount = std::filesystem::remove_all(entry.path(), removeError);
        if (removedCount > 0 && !removeError) {
            if (entry.is_directory(sizeError)) ++result.directoriesRemoved;
            else ++result.filesRemoved;
            result.bytesFreed += size;
        } else {
            ++result.skipped;
            ++result.lockedSkipped;
        }
    }
    return result;
}

void printCleanupResult(const CleanupResult& result) {
    std::cout << "TEMP Cleanup Result\n-------------------\n";
    if (result.dryRun) {
        std::cout << "Dry-run candidates : " << result.candidates << '\n'
                  << "Potential bytes    : " << result.candidateBytes << '\n'
                  << "Protected skipped  : " << result.protectedSkipped << '\n'
                  << "Recent skipped     : " << result.recentSkipped << '\n'
                  << "No files changed.\n";
        return;
    }
    std::cout << "Files removed      : " << result.filesRemoved << '\n'
              << "Directories removed: " << result.directoriesRemoved << '\n'
              << "Skipped/locked     : " << result.skipped << '\n'
              << "Protected skipped  : " << result.protectedSkipped << '\n'
              << "Recent skipped     : " << result.recentSkipped << '\n'
              << "Locked/failed      : " << result.lockedSkipped << '\n'
              << "Bytes freed        : " << result.bytesFreed << '\n';
}

} // namespace handler
