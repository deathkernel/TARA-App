# Batch 19 — Voice and vision adapters

## Scope
- Whisper: optional local speech-to-text backend behind the existing TARA Voice interface.
- CLIP: separate image/text similarity-search capability; do not replace image understanding.
- Shap-E: experimental 3D-generation lab only, outside core runtime.

## Dependency boundaries
Each capability has its own optional dependency group and availability check. Do not install large model frameworks for users who do not enable the feature. Model weights are downloaded only after an explicit action and with size/license details displayed.

## Implementation files expected
- Adapter interfaces for transcription and image/text embedding/search.
- Feature availability metadata and bounded request validation.
- Mock-based tests for absent packages, invalid inputs, timeout, and inference errors.
- Separate experimental entry point for Shap-E, if approved after license/runtime review.

## Acceptance checks
- Chat and app startup work without all three capabilities.
- Existing voice and vision paths remain intact.
- No media is uploaded to a remote service by these local adapters.
- File sizes, supported formats, model download, compute needs, and known limitations are documented.
- CI never downloads model weights.

## Non-goals
Do not claim GPU support without verification; do not bundle 3D research dependencies in the default install.