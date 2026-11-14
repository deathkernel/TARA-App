# SITA — Smart Intelligence & Thinking Assistant

SITA is the product and assistant brand for this project.

- **Product name:** SITA
- **Official expansion:** Smart Intelligence & Thinking Assistant
- **Underlying cognitive architecture:** TN-86B
- **LLM gateway:** OmniRoute (the only configured language-model gateway)

## Product and architecture boundary

SITA is the user-facing assistant and application. TN-86B is the brain-inspired cognitive architecture developed to power SITA. TN-86B is not a claim to simulate 86 billion biological neurons; its name references the approximate neuron count used as an architectural inspiration.

## Repository and compatibility

The source repository is currently named `deathkernel/TARA-App`; the repository URL/name can be updated separately. The following technical identifiers are intentionally retained for compatibility and are not the product brand:

- Python import namespaces such as `tara_app`, `tara_chat`, and `tara_code`
- Distribution name `tara-app-core` and legacy `tara-app` CLI entry point
- Existing `tara-app.toml` configuration filename and `TARA_*` environment-variable prefix
- Existing launcher filenames `run-tara.bat` and `run-tara.sh`
- Existing local storage keys and persisted data identifiers

A new `sita` CLI entry point is provided alongside the legacy `tara-app` command. Do not rename compatibility identifiers without a separately planned migration.

## Naming rules

- Use **SITA** in user-facing UI, assistant prompts, help text, product documentation, and release descriptions.
- Use **TN-86B** for the underlying cognitive architecture.
- Use **OmniRoute** for the existing language-model gateway.
- Keep repository paths, package names, environment variables, and historical commit records unchanged unless a migration explicitly requires it.
