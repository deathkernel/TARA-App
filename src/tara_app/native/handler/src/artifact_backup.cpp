#include "handler/artifact_backup.h"

#include <fstream>
#include <functional>
#include <cstdint>
#include <iomanip>
#include <sstream>

namespace handler {

namespace {
std::optional<std::uint64_t> contentFingerprint(
    const std::filesystem::path& file) {
    std::ifstream input(file, std::ios::binary);
    if (!input) return std::nullopt;

    constexpr std::uint64_t offset = 1469598103934665603ULL;
    constexpr std::uint64_t prime = 1099511628211ULL;
    std::uint64_t hash = offset;
    char buffer[8192];
    while (input.read(buffer, sizeof(buffer)) || input.gcount() > 0) {
        const auto count = input.gcount();
        for (std::streamsize i = 0; i < count; ++i) {
            hash ^= static_cast<unsigned char>(buffer[i]);
            hash *= prime;
        }
    }
    if (input.bad()) return std::nullopt;
    return hash;
}
}


std::optional<ArtifactBackup> backupArtifact(
    const std::filesystem::path& source,
    const std::filesystem::path& backupRoot) {
    std::error_code ec;
    const bool exists = std::filesystem::is_regular_file(source, ec);
    if (ec) return std::nullopt;

    std::filesystem::create_directories(backupRoot, ec);
    if (ec) return std::nullopt;

    const auto name = source.filename().string();
    const auto canonicalSource = std::filesystem::weakly_canonical(source, ec);
    if (ec) return std::nullopt;
    const auto digest = std::hash<std::string>{}(canonicalSource.string());
    std::ostringstream suffix;
    suffix << std::hex << digest;
    const auto backup = backupRoot / (name + "." + suffix.str() + ".bak");
    if (exists) {
        std::filesystem::copy_file(
            source, backup, std::filesystem::copy_options::overwrite_existing, ec);
        if (ec) return std::nullopt;
    }
    std::uintmax_t size = 0;
    std::uint64_t fingerprint = 0;
    if (exists) {
        size = std::filesystem::file_size(source, ec);
        if (ec) return std::nullopt;
        const auto hash = contentFingerprint(source);
        if (!hash) return std::nullopt;
        fingerprint = *hash;
    }
    return ArtifactBackup{source, backup, exists, size, exists ? size : 0, fingerprint};
}

bool restoreArtifact(const ArtifactBackup& backup) {
    std::error_code ec;
    if (backup.existed) {
        if (!std::filesystem::is_regular_file(backup.backup, ec) || ec) return false;
        const auto backupSize = std::filesystem::file_size(backup.backup, ec);
        if (ec || backupSize != backup.backupSize) return false;
        const auto backupHash = contentFingerprint(backup.backup);
        if (!backupHash || *backupHash != backup.contentHash) return false;
        std::filesystem::copy_file(
            backup.backup, backup.original,
            std::filesystem::copy_options::overwrite_existing, ec);
        if (ec) return false;
        const auto restoredSize = std::filesystem::file_size(backup.original, ec);
        if (ec || restoredSize != backup.originalSize) return false;
        const auto restoredHash = contentFingerprint(backup.original);
        return restoredHash && *restoredHash == backup.contentHash;
    }
    std::filesystem::remove(backup.original, ec);
    return !ec || !std::filesystem::exists(backup.original);
}

} // namespace handler
