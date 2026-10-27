#include "handler/safe_mode.h"
namespace handler {
SafeModeContext createSafeModeContext(const std::filesystem::path& base) {
    SafeModeContext c; c.root = base / ".handler-sandbox"; std::error_code ec; std::filesystem::create_directories(c.root, ec); c.enabled = !ec; return c;
}
bool safePathAllowed(const SafeModeContext& context, const std::filesystem::path& target) {
    if (!context.enabled) return false;
    std::error_code ec;
    const auto root = std::filesystem::weakly_canonical(context.root, ec);
    const auto path = std::filesystem::weakly_canonical(target, ec);
    if (ec) return false;
    auto mismatch = std::mismatch(root.begin(), root.end(), path.begin(), path.end());
    return mismatch.first == root.end();
}
}