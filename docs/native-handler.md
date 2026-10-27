# Native TARA-Handler integration

TARA-App includes the C++17 sources from [TARA-Handler](https://github.com/deathkernel/TARA-Handler), pinned at source revision `617d3bbf10a0bd37dbc69604c405840b9bdb1a4b`.

## Build and launch

The Windows and macOS/Linux launchers run the explicit `tara_app.handler_launcher prepare` step before opening TARA-App. That step builds into the user's local TARA cache with CMake when a C++ toolchain is available. It does not download code or models. If native compilation is unavailable, the launch continues and the Handler capability uses read-only Python diagnostics.

For manual setup, install CMake and a C++17 compiler, install TARA-App, then run:

```sh
python -m tara_app.handler_launcher prepare
```

The app never compiles native code during a conversation. A prepared binary is reused while the packaged source fingerprint is unchanged.

## App boundary

TARA-App only passes the fixed `doctor` command to Handler. The existing repair, cleanup, uninstall, recovery, rollback, and command-execution subcommands are not reachable through the app adapter. The vendored `doctor` route omits Handler's history write so it remains read-only. If native build tools are missing, the Python fallback reports operating system, available developer tools, local port status, and the nearest project marker without changing files.

The native binary runs with a bounded timeout, no stdin, a filtered process environment, and captured output. It is built into the user's cache, not inside the installed Python package.
