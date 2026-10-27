#pragma once

#include <filesystem>

namespace handler {

// Returns true when child is the same as, or below, root after canonicalization.
bool pathUnder(const std::filesystem::path& child,
               const std::filesystem::path& root);

// Validates an executable against Handler's platform trust boundary.
// Windows accepts known system/application install roots; Unix/macOS accepts
// existing executables unless they live inside the current project tree.
bool isTrustedExecutablePath(const std::filesystem::path& path);

} // namespace handler
