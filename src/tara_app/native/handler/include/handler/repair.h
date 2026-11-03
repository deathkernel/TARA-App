#pragma once

namespace handler {

inline constexpr int kRepairCancelled = 2;

int repairPythonModule(const char* package);
int repairNodeModule(const char* package);

} // namespace handler
