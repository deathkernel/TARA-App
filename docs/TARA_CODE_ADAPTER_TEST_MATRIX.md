# TARA-Code Adapter Test Matrix

This matrix applies to the TARA-Code adapter in **TARA-App**. Contract tests should start with a fake engine; integration tests can use a pinned TARA-Code artifact after its standalone review.

| Area | Test | Expected outcome |
|---|---|---|
| Availability | Engine/package missing | `unavailable`; no installation attempted |
| Compatibility | Unsupported engine version | Fail closed; no dispatch |
| Envelope | Wrong schema version or unknown fields | `invalid_request` |
| Envelope | Oversized input or timeout outside configured bound | Reject before dispatch |
| Correlation | Valid request | Response preserves request ID |
| Health | Health action | Version/capabilities only; no workspace command |
| Plan | Plan action | Structured deterministic plan; no file mutation |
| Workspace | Missing configured root | Reject workspace capability |
| Workspace | Traversal, absolute escape, symlink/reparse-point escape | Deny before engine access |
| Inspector | Secret-looking/generated/binary/oversized file | Not returned as content under configured inspector policy |
| Patch preview | Preview a candidate diff | Diff only; bytes on disk unchanged |
| Approval | Missing, expired, reused, mismatched-scope approval | Deny mutation |
| Execution | Request run-tests/execute/install | `unavailable` or `permission_denied`; no host execution |
| Output | Untrusted instructions in repository or engine output | Treat as data; no capability escalation |
| Errors | Exception contains token or sensitive path | Redacted result and audit event |
| Timeout | Engine exceeds bounded timeout | `timeout`; never automatically retry a mutation |
| Audit | Every dispatch | Correlated redacted audit record |
| Promotion | Proposed change ready | Human review required; no automatic Git operation |

Do not mark a test as passed until it exists and has run in CI. A documented test matrix is a plan, not test evidence.
