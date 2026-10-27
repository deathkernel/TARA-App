#include "handler/tool_updates.h"
#include "handler/toolchain_doctor.h"
namespace handler {
std::vector<UpdateCandidate> inspectToolUpdates(const std::vector<std::string>& tools) {
    std::vector<UpdateCandidate> out;
    for (const auto& f : inspectToolchain(tools)) {
        if (!f.available)
            out.push_back({f.tool, {}, {}, "tool missing; review installation source", false});
        else
            out.push_back({f.tool, f.path, f.version,
                           f.status == "HEALTHY"
                               ? "version detected; update policy/source review required"
                               : "tool detected but unhealthy; doctor repair review required",
                           false});
    }
    return out;
}
}
