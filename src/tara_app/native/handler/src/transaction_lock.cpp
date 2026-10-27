#include "handler/transaction_lock.h"

#include <system_error>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif

namespace handler {

TransactionLock::TransactionLock(std::filesystem::path file)
    : file_(std::move(file)) {}

TransactionLock::~TransactionLock() {
    release();
}

bool TransactionLock::acquire() {
    if (held())
        return true;

    std::error_code ec;
    if (!file_.parent_path().empty())
        std::filesystem::create_directories(file_.parent_path(), ec);
    if (ec)
        return false;

#ifdef _WIN32
    const auto native = file_.wstring();
    HANDLE handle = CreateFileW(
        native.c_str(), GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE)
        return false;

    OVERLAPPED overlapped{};
    if (!LockFileEx(handle, LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY,
                    0, MAXDWORD, MAXDWORD, &overlapped)) {
        CloseHandle(handle);
        return false;
    }

    handle_ = handle;
    return true;
#else
    fd_ = ::open(file_.c_str(), O_RDWR | O_CREAT, 0600);
    if (fd_ < 0)
        return false;

    if (::flock(fd_, LOCK_EX | LOCK_NB) != 0) {
        ::close(fd_);
        fd_ = -1;
        return false;
    }

    return true;
#endif
}

void TransactionLock::release() {
#ifdef _WIN32
    if (handle_) {
        OVERLAPPED overlapped{};
        UnlockFileEx(static_cast<HANDLE>(handle_), 0, MAXDWORD, MAXDWORD, &overlapped);
        CloseHandle(static_cast<HANDLE>(handle_));
        handle_ = nullptr;
    }
#else
    if (fd_ >= 0) {
        ::flock(fd_, LOCK_UN);
        ::close(fd_);
        fd_ = -1;
    }
#endif
}

bool TransactionLock::held() const noexcept {
#ifdef _WIN32
    return handle_ != nullptr;
#else
    return fd_ >= 0;
#endif
}

} // namespace handler
