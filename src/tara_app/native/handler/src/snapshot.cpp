#include "handler/snapshot.h"

#include <chrono>
#include <cctype>
#include <fstream>
#include <sstream>
#include <utility>
#include <algorithm>

namespace handler {

namespace {
bool containsLineBreak(const std::string& value) {
    return value.find('\n') != std::string::npos ||
           value.find('\r') != std::string::npos;
}

std::string snapshotId() {
    const auto now = std::chrono::system_clock::now();
    const auto stamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()).count();
    return std::to_string(stamp);
}
}

SnapshotStore::SnapshotStore(std::filesystem::path root) : root_(std::move(root)) {}

std::optional<SnapshotInfo> SnapshotStore::create(const EnvironmentState& state) const {
    // Snapshot records are line-oriented key/value pairs. Reject values that
    // could inject additional fields or make the snapshot impossible to parse.
    if (containsLineBreak(state.timestampUtc) ||
        containsLineBreak(state.computerName) ||
        containsLineBreak(state.userName) ||
        containsLineBreak(state.tempPath) ||
        containsLineBreak(state.pathValue) ||
        containsLineBreak(state.currentDirectory.string()) ||
        containsLineBreak(state.handlerVersion))
        return std::nullopt;

    std::error_code ec;
    std::filesystem::create_directories(root_, ec);
    if (ec) return std::nullopt;

    const std::string baseId = snapshotId();
    std::string id = baseId;
    std::error_code collisionEc;
    for (unsigned int suffix = 1;; ++suffix) {
        const bool exists = std::filesystem::exists(root_ / (id + ".state"), collisionEc);
        if (collisionEc) return std::nullopt;
        if (!exists) break;
        id = baseId + "-" + std::to_string(suffix);
    }
    const auto path = root_ / (id + ".state");
    std::ofstream out(path, std::ios::trunc);
    if (!out) return std::nullopt;

    out << "timestamp_utc=" << state.timestampUtc << '\n'
        << "computer_name=" << state.computerName << '\n'
        << "user_name=" << state.userName << '\n'
        << "temp_path=" << state.tempPath << '\n'
        << "path=" << state.pathValue << '\n'
        << "current_directory=" << state.currentDirectory.string() << '\n'
        << "handler_version=" << state.handlerVersion << '\n';

    out.flush();
    const bool writeSucceeded = out.good();
    out.close();
    if (!writeSucceeded || out.fail()) {
        std::error_code cleanupEc;
        std::filesystem::remove(path, cleanupEc);
        return std::nullopt;
    }
    return SnapshotInfo{id, path};
}

std::optional<EnvironmentState> SnapshotStore::load(const SnapshotInfo& snapshot) const {
    if (snapshot.id.empty() || snapshot.id.size() > 64 ||
        !std::all_of(snapshot.id.begin(), snapshot.id.end(),
                     [](unsigned char ch) { return std::isdigit(ch) || ch == '-'; }))
        return std::nullopt;

    std::error_code ec;
    const auto canonicalRoot = std::filesystem::weakly_canonical(root_, ec);
    if (ec) return std::nullopt;
    const auto canonicalPath = std::filesystem::weakly_canonical(snapshot.path, ec);
    if (ec || canonicalPath.parent_path() != canonicalRoot ||
        canonicalPath.filename() != snapshot.id + ".state")
        return std::nullopt;

    std::ifstream in(canonicalPath);
    if (!in) return std::nullopt;

    EnvironmentState state;
    bool timestampSeen = false;
    bool computerSeen = false;
    bool userSeen = false;
    bool tempSeen = false;
    bool pathSeen = false;
    bool directorySeen = false;
    bool versionSeen = false;
    std::string line;
    while (std::getline(in, line)) {
        const auto pos = line.find('=');
        if (pos == std::string::npos) return std::nullopt;
        const auto key = line.substr(0, pos);
        const auto value = line.substr(pos + 1);

        if (key == "timestamp_utc" && !timestampSeen) {
            state.timestampUtc = value; timestampSeen = true;
        } else if (key == "computer_name" && !computerSeen) {
            state.computerName = value; computerSeen = true;
        } else if (key == "user_name" && !userSeen) {
            state.userName = value; userSeen = true;
        } else if (key == "temp_path" && !tempSeen) {
            state.tempPath = value; tempSeen = true;
        } else if (key == "path" && !pathSeen) {
            state.pathValue = value; pathSeen = true;
        } else if (key == "current_directory" && !directorySeen) {
            state.currentDirectory = value; directorySeen = true;
        } else if (key == "handler_version" && !versionSeen) {
            state.handlerVersion = value; versionSeen = true;
        } else {
            return std::nullopt;
        }
    }
    if (in.bad()) return std::nullopt;
    if (!timestampSeen || !computerSeen || !userSeen || !tempSeen ||
        !pathSeen || !directorySeen || !versionSeen || state.currentDirectory.empty())
        return std::nullopt;
    return state;
}

std::vector<SnapshotInfo> SnapshotStore::list() const {
    std::vector<SnapshotInfo> snapshots;
    std::error_code ec;
    if (!std::filesystem::exists(root_, ec)) return snapshots;
    for (const auto& entry : std::filesystem::directory_iterator(root_, ec)) {
        if (ec) break;
        if (!entry.is_regular_file() || entry.path().extension() != ".state") continue;
        snapshots.push_back({entry.path().stem().string(), entry.path()});
    }
    std::sort(snapshots.begin(), snapshots.end(),
              [](const auto& a, const auto& b) { return a.id > b.id; });
    return snapshots;
}

std::optional<SnapshotInfo> SnapshotStore::find(const std::string& id) const {
    if (id.empty() || id.size() > 64 ||
        !std::all_of(id.begin(), id.end(),
                     [](unsigned char ch) { return std::isdigit(ch) || ch == '-'; }))
        return std::nullopt;
    const auto path = root_ / (id + ".state");
    std::error_code ec;
    if (!std::filesystem::is_regular_file(path, ec)) return std::nullopt;
    return SnapshotInfo{id, path};
}

} // namespace handler
