# SN-86B Phase 6 — MMI (Multimodal Integration)

**Status:** Initial adapter and cognitive bridge implementation committed; automated execution and live-app integration validation pending.

## Objective

Normalize existing SITA text, voice-transcription and vision-analysis outputs into bounded, typed observations that can enter the existing Cognitive Engine context pipeline.

## Components

| Short form | Component | Responsibility |
|---|---|---|
| MMI | Multimodal Integration | Shared observation contracts and modality boundaries |
| NIP | Normalized Input Pipeline | Validates and converts specialist outputs |
| VPI | Voice Processing Integration | Accepts successful local SITA Voice transcripts |
| VSI | Vision Signal Integration | Accepts successful SITA Vision analysis returned through OmniRoute |
| MCB | Multimodal Cognitive Bridge | Passes transient observations to the CognitiveCoordinator |

## Data flow

```text
User audio -> SITA Voice (local Whisper) -> transcript ---+
                                                          |
User image -> SITA Vision -> OmniRoute -> analysis -------+-> NIP -> typed observations
                                                          |             |
User text ------------------------------------------------+             v
                                                               MCB / Cognitive Engine
                                                                       |
                                                             bounded context + attention
```

The bridge is an explicit integration boundary. It does not dispatch specialists, call an LLM, execute tools, grant approvals, write long-term memory, or retain original media bytes.

## Privacy and routing boundary

- Voice transcripts are accepted only when the existing voice specialist reports `local: true`.
- Vision analysis is accepted only when the existing vision specialist reports `provider: omniroute`.
- Existing SITA Vision currently marks `images_sent_to_remote: true`; image bytes are sent to the configured OmniRoute endpoint. Whether that endpoint forwards data to an external model provider depends on the user's OmniRoute deployment and route. Do not describe this path as on-device-only.
- Only bounded text and limited metadata enter the cognitive context. Raw audio/image payloads are not copied into SN-86B observations.
- Observations are transient. The bridge does not persist them or consolidate them into episodic/semantic memory.
- Specialist errors and unavailable results are rejected rather than converted into context.
- Content from images and transcripts remains untrusted user content, not instructions or authorization.

## Bounded contracts

- At most 16 observations per batch.
- At most 80,000 aggregate characters per batch.
- At most 20,000 characters per observation.
- Observation IDs must be unique within a batch.
- Confidence values are bounded engineering weights, not calibrated probabilities.
- No raw media, credentials, approval tokens or provider secrets are accepted by the observation contract.

## Implementation boundary

The `MultimodalInputPipeline` adapts already-produced specialist result envelopes. The `MultimodalCognitiveBridge` converts observations to the existing `ContextItem` contract and calls `CognitiveCoordinator.process`. Existing SITA orchestration remains responsible for selecting and invoking voice/vision specialists. This phase does not silently modify the live Orchestrator dispatch path.

## Verification

Focused tests cover malformed observations, confidence validation, local voice provenance, OmniRoute vision provenance, failed specialist responses, duplicate IDs, batch limits, context conversion, and no-action-abstention behavior.

Tests are authored but have not yet been executed in the target repository environment. CI and runtime integration must be checked before claiming this phase is validated.

## Known limitations

- Voice and vision results must be supplied by the caller; no live event bus or automatic attachment-to-cognition hook is introduced.
- Confidence values for voice and vision are conservative fixed engineering weights, not recognizer/model confidence estimates.
- Vision text is a model-generated description and may be incorrect; it is not treated as verified visual ground truth.
- No automatic memory write, learning update, or action execution occurs.
