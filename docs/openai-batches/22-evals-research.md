# Batch 22 — Evaluations and research-only repositories

## Scope
Use `openai/evals`, `openai/frontier-evals`, `openai/openai-cookbook`, and `openai/tiktoken` for selectively adapted test fixtures/utilities. Keep `openai/gpt-2`, `openai/spinningup`, `openai/gym`, and `openai/procgen` in isolated research/education workflows. Treat `openai/gym` as archived and do not add it as a new production dependency.

## Implementation files expected
- Deterministic offline evaluation fixtures with explicit expected outcomes.
- Optional token-count utility labelled by tokenizer/encoding; never assume all providers share tokenization.
- Separate research environment/requirements file if a concrete experiment is approved.
- CI job that runs offline tests by default; hosted-model evaluations require an explicit opt-in and cost label.

## Acceptance checks
- Default CI requires no API keys and no network inference.
- Evaluation fixtures avoid unstable exact wording when semantic assertions are more appropriate.
- Research dependencies do not enter core package metadata.
- Every adapted upstream example records its source and applicable license.
- No training workload or large model download is triggered by app startup or CI.

## Non-goals
Do not import entire repositories, run benchmark suites silently, or present research prototypes as production-ready integrations.