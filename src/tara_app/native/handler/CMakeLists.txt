cmake_minimum_required(VERSION 3.20)
project(TARAHandler VERSION 0.9.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(tara-handler
    src/action_engine.cpp
    src/artifact_backup.cpp
    src/auto_recovery.cpp
    src/circuit_breaker.cpp
    src/command_engine.cpp
    src/component_discovery.cpp
    src/decision_engine.cpp
    src/deep_cleanup.cpp
    src/dependency_graph.cpp
    src/dependency_manager.cpp
    src/environment_guardian.cpp
    src/environment_health.cpp
    src/environment_state.cpp
    src/error_detection.cpp
    src/executable_trust.cpp
    src/history.cpp
    src/main.cpp
    src/maintenance.cpp
    src/module.cpp
    src/path_guardian.cpp
    src/policy.cpp
    src/project_context.cpp
    src/recovery.cpp
    src/recovery_journal.cpp
    src/repair.cpp
    src/resource_guardian.cpp
    src/risky_command.cpp
    src/router.cpp
    src/safe_mode.cpp
    src/snapshot.cpp
    src/state_paths.cpp
    src/state_store.cpp
    src/system_info.cpp
    src/temp_cleaner.cpp
    src/tool_updates.cpp
    src/toolchain_doctor.cpp
    src/transaction.cpp
    src/transaction_lock.cpp
    src/uninstall.cpp
    src/verification.cpp
)

target_include_directories(tara-handler PRIVATE include)
if(WIN32)
    target_compile_definitions(tara-handler PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
    target_link_libraries(tara-handler PRIVATE Ws2_32)
endif()
if(MSVC)
    target_compile_options(tara-handler PRIVATE /W4 /permissive-)
else()
    target_compile_options(tara-handler PRIVATE -Wall -Wextra -Wpedantic)
endif()
set_target_properties(tara-handler PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL "${CMAKE_BINARY_DIR}/bin"
)
