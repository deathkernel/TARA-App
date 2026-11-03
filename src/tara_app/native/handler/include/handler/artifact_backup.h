#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>

namespace handler {

struct ArtifactBackup {
    std::filesystem::path original;
    std::filesystem::path backup;
    bool existed{false};
    std::uintmax_t originalSize{0};
    std::uintmax_t backupSize{0};
    std::uint64_t contentHash{0};
};

std::optional<ArtifactBackup> backupArtifact(
    const std::filesystem::path& source,
    const std::filesystem::path& backupRoot);

bool restoreArtifact(const ArtifactBackup& backup);

} // namespace handler
