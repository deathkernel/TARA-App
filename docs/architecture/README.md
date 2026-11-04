# TARA Architecture Blueprint

**Status:** Proposed architecture for review. This folder documents the target design; it does not claim that source code has been migrated.

## Documents

1. [System Design](SYSTEM_DESIGN.md) — system boundaries, responsibility-oriented structure, dependency direction, data ownership, security and reliability.
2. [Canonical Data Flow](DATA_FLOW.md) — request lifecycle, workflow context, step contracts, result propagation and failure behavior.
3. [Architecture Decisions](ARCHITECTURE_DECISIONS.md) — the decisions that prevent model-centric and feature-centric organization.
4. [Migration Plan](MIGRATION_PLAN.md) — evidence-first, test-gated sequence for moving the existing code safely.

## Review order

Read System Design first, then Data Flow, Decisions, and Migration Plan. The existing [architecture document](../ARCHITECTURE.md) describes parts of the current implementation; this folder describes the proposed target. Where the two differ, do not assume the target is already implemented.

## Current implementation is not changed

This blueprint adds documentation only. It does not move source files, change runtime behavior, change dependencies, alter model/provider routing, or relax security policy.
