#include "handler/executable_trust.h"

#include <cstdlib>
#include <system_error>

#ifdef _WIN32
#include <cwchar>
#endif

namespace handler {

namespace {

bool pathComponentEqual(const std::filesystem::path& left,
                        const std::filesystem::path& right) {
#ifdef _WIN32
    return _wcsicmp(left.wstring().c_str(), right.wstring().c_str()) == 0;
#else
    return left == right;
#endif
}

#ifdef _WIN32
bool trustedWindowsRoot(const std::filesystem::path& canonical) {
    const char* pf = std::getenv("ProgramFiles");
    const char* pf86 = std::getenv("ProgramFiles(x86)");
    const char* localAppData = std::getenv("LOCALAPPDATA");
    const char* windowsRoot = std::getenv("WINDIR");

    const std::filesystem::path roots[] = {
        pf && *pf ? std::filesystem::path(pf) : std::filesystem::path{},
        pf86 && *pf86 ? std::filesystem::path(pf86) : std::filesystem::path{},
        localAppData && *localAppData
            ? std::filesystem::path(localAppData) / "Programs"
            : std::filesystem::path{},
        localAppData && *localAppData
            ? std::filesystem::path(localAppData) / "Microsoft" / "WindowsApps"
            : std::filesystem::path{},
        windowsRoot && *windowsRoot
            ? std::filesystem::path(windowsRoot) / "System32"
            : std::filesystem::path{},
        windowsRoot && *windowsRoot
            ? std::filesystem::path(windowsRoot) / "SysWOW64"
            : std::filesystem::path{}
    };

    for (const auto& root : roots) {
        if (!root.empty() && pathUnder(canonical, root))
            return true;
    }
    return false;
}
#endif

} // namespace

bool pathUnder(const std::filesystem::path& child,
               const std::filesystem::path& root) {
    std::error_code ec;
    const auto canonicalChild = std::filesystem::weakly_canonical(child, ec);
    if (ec) return false;

    ec.clear();
    const auto canonicalRoot = std::filesystem::weakly_canonical(root, ec);
    if (ec) return false;

    auto childIt = canonicalChild.begin();
    auto rootIt = canonicalRoot.begin();
    for (; rootIt != canonicalRoot.end() && childIt != canonicalChild.end();
         ++rootIt, ++childIt) {
        if (!pathComponentEqual(*rootIt, *childIt))
            return false;
    }
    return rootIt == canonicalRoot.end();
}

bool isTrustedExecutablePath(const std::filesystem::path& path) {
    std::error_code ec;
    const auto canonical = std::filesystem::weakly_canonical(path, ec);
    if (ec || canonical.empty() ||
        !std::filesystem::is_regular_file(canonical, ec))
        return false;

    ec.clear();
    const auto current = std::filesystem::weakly_canonical(
        std::filesystem::current_path(), ec);
    if (!ec && pathUnder(canonical, current))
        return false;

#ifdef _WIN32
    return trustedWindowsRoot(canonical);
#else
    return true;
#endif
}

} // namespace handler
