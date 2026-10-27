# Sandbox policy hardening

The coding-agent policy gate is a **policy check**, not an operating-system sandbox. Execution must still happen in a real isolated runner/container with resource limits and an explicit filesystem/network policy.

- Approval and isolation are always required.
- Network access is denied unless the sandbox grants it and the operation declares it needs it.
- Writes are denied unless the sandbox grants write access and the operation declares it needs it.
- Capability flags reject non-boolean values rather than treating truthy values as permission.
- This module does not execute commands or create a sandbox; callers must enforce the returned decision at the execution boundary.
