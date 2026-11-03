#include "handler/state_paths.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <cwctype>

namespace handler {

std::filesystem::path handlerStateRoot() {
#ifdef _WIN32
    if (const char* p = std::getenv("LOCALAPPDATA"); p && *p)
        return std::filesystem::path(p) / "Handler";
    if (const char* p = std::getenv("USERPROFILE"); p && *p)
        return std::filesystem::path(p) / ".handler";
#else
    if (const char* p = std::getenv("XDG_STATE_HOME"); p && *p)
        return std::filesystem::path(p) / "handler";
    if (const char* p = std::getenv("HOME"); p && *p)
        return std::filesystem::path(p) / ".local" / "state" / "handler";
#endif
    return std::filesystem::current_path() / ".handler";
}

std::filesystem::path handlerTransactionRoot() {
    return handlerStateRoot() / "transactions";
}

bool isHandlerStatePath(const std::filesystem::path& file) {
    std::error_code ec;
    const auto rootPath = handlerStateRoot();
    if (!std::filesystem::exists(rootPath, ec) || ec) return false;
    const auto root = std::filesystem::weakly_canonical(rootPath, ec);
    if (ec || root.empty()) return false;
    ec.clear();
    const auto candidate = std::filesystem::weakly_canonical(file, ec);
    if (ec || candidate.empty()) return false;

    auto rootIt = root.begin();
    auto candidateIt = candidate.begin();
    for (; rootIt != root.end() && candidateIt != candidate.end(); ++rootIt, ++candidateIt) {
#ifdef _WIN32
        std::wstring a = rootIt->wstring();
        std::wstring b = candidateIt->wstring();
        if (a.size() != b.size()) return false;
        for (std::size_t i = 0; i < a.size(); ++i) {
            if (std::towlower(a[i]) != std::towlower(b[i])) return false;
        }
#else
        if (*rootIt != *candidateIt) return false;
#endif
    }
    return rootIt == root.end();
}

} // namespace handler
