#include "handler/maintenance.h"

#include <iostream>
#include <thread>

namespace handler {

MaintenanceLoop::MaintenanceLoop(std::chrono::hours interval)
    : interval_(interval) {}

void MaintenanceLoop::run(const std::function<void()>& task) const {
    if (!task) {
        std::cerr << "Maintenance loop skipped: no task configured.\n";
        return;
    }
    std::cout << "Maintenance loop active. Interval: "
              << interval_.count() << " hours.\n";

    while (true) {
        task();
        std::cout << "Handler entering idle state until the next maintenance event.\n";
        std::this_thread::sleep_for(interval_);
    }
}

} // namespace handler
