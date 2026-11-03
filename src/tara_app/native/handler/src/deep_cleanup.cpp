#include "handler/deep_cleanup.h"
namespace handler {
CleanupSummary deepCleanup(const std::filesystem::path& root, bool backupFirst) {
    CleanupSummary out;
    if (backupFirst) return out;
    std::error_code ec;
    if (!std::filesystem::is_directory(root, ec)) return out;
    for (const auto& e : std::filesystem::directory_iterator(root, ec)) {
        if (ec) break;
        if (e.is_regular_file(ec)) { out.bytes += e.file_size(ec); std::filesystem::remove(e.path(), ec); if (!ec) ++out.files; else ++out.skipped; }
    }
    return out;
}
}