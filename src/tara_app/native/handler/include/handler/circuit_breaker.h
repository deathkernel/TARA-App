#pragma once

namespace handler {

class RecoveryCircuitBreaker {
public:
    explicit RecoveryCircuitBreaker(int maxFailures = 3);
    bool allow() const;
    void recordFailure();
    void reset();

private:
    int maxFailures_;
    int failures_{0};
};

} // namespace handler
