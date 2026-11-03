#pragma once
#include <filesystem>

namespace handler {

// Single source of truth for Handler-owned persistent state.
std::filesystem::path handlerStateRoot();
std::filesystem::path handlerTransactionRoot();

// Baseline/state files are trusted only when they live inside Handler-owned state.
bool isHandlerStatePath(const std::filesystem::path& file);

} // namespace handler
