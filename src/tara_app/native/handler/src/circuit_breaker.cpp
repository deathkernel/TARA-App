#include "handler/circuit_breaker.h"

namespace handler {

RecoveryCircuitBreaker::RecoveryCircuitBreaker(int maxFailures)
    : maxFailures_(maxFailures > 0 ? maxFailures : 1) {}

bool RecoveryCircuitBreaker::allow() const { return failures_ < maxFailures_; }

void RecoveryCircuitBreaker::recordFailure() {
    if (failures_ < maxFailures_) ++failures_;
}

void RecoveryCircuitBreaker::reset() { failures_ = 0; }

} // namespace handler
