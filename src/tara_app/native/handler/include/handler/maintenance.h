#pragma once

#include <chrono>
#include <functional>

namespace handler {

class MaintenanceLoop {
public:
    explicit MaintenanceLoop(std::chrono::hours interval);
    void run(const std::function<void()>& task) const;

private:
    std::chrono::hours interval_;
};

} // namespace handler
