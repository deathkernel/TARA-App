#pragma once

#include <filesystem>

namespace handler {

// Process-wide transaction lock. The operating system releases the underlying
// lock when the owning process exits, so a crashed Handler does not strand a
// permanently stale lock file.
class TransactionLock {
public:
    explicit TransactionLock(std::filesystem::path file);
    ~TransactionLock();

    TransactionLock(const TransactionLock&) = delete;
    TransactionLock& operator=(const TransactionLock&) = delete;

    bool acquire();
    void release();
    bool held() const noexcept;

private:
    std::filesystem::path file_;
#ifdef _WIN32
    void* handle_{nullptr};
#else
    int fd_{-1};
#endif
};

} // namespace handler
