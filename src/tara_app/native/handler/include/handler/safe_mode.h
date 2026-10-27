#pragma once
#include <filesystem>
#include <string>
namespace handler {
struct SafeModeContext { bool enabled{false}; std::filesystem::path root; };
SafeModeContext createSafeModeContext(const std::filesystem::path& base);
bool safePathAllowed(const SafeModeContext& context, const std::filesystem::path& target);
}