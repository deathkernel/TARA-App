# Runtime and Development Options

Research notes checked on 2026-10-26. These products are optional references; TARA-App does not install, invoke, or depend on them automatically.

## Amp

Amp's current documentation describes a coding agent and development environment that can work from the web, apps, and terminal. Treat Amp as an optional way to develop or review TARA repositories. It is not a TARA model provider or a dependency of the TARA-App runtime. The product documentation reviewed here does not establish that all Amp usage is free, so do not make a free-use claim in TARA setup instructions.

Source: [Amp documentation](https://ampcode.com/docs).

## GitHub Copilot local sandboxing

GitHub describes local sandboxing for Copilot CLI, the Copilot app, and supported VS Code Agent Host sessions. Its local sandbox policy can limit filesystem access, network access, and credential use. GitHub announced local sandboxing as generally available and included with Copilot at no additional cost. This is a useful reference for the future TARA-Code execution boundary, but it does not mean TARA-Code currently invokes Copilot or inherits its sandbox. Keep TARA-Code execution disabled until its own configured runner has verified isolation and policy enforcement.

Sources: [GitHub local sandbox announcement](https://github.blog/changelog/2026-10-07-local-sandboxing-for-github-copilot-now-generally-available/), [GitHub sandbox configuration guide](https://docs.github.com/en/copilot/how-tos/cloud-and-local-sandboxes/configuring-local-sandbox-settings).

## GitHub Package Firewall

GitHub's Package Firewall is in public preview for GitHub Enterprise Cloud customers, is free during the preview, and currently supports npm. It may help protect dependency installation on eligible TARA development machines or CI runners, but it is not a baseline feature for users without Enterprise Cloud access and it does not cover the Python packages used by the current modules.

Sources: [GitHub preview announcement](https://github.blog/changelog/2026-10-20-github-package-firewall-in-public-preview/), [Package Firewall documentation](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/protecting-endpoints-with-package-firewall).

## AWS TorchNeuron

AWS documents TorchNeuron as a native PyTorch backend for Trainium, currently in public beta for Trainium2 and Trainium3. It is relevant only when TARA's model runtime is deployed on supported AWS hardware with a compatible PyTorch model and software stack. Keep it as a hardware-specific optional backend; it is not a general local inference runtime and should not be presented as free cloud compute.

Sources: [TorchNeuron overview](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/torch/about-pytorch-neuron.html), [Neuron 2.33 TorchNeuron release notes](https://awsdocs-neuron.readthedocs-hosted.com/en/v2.33.0/release-notes/components/torchneuron.html).

## TARA integration decisions

- TARA-App owns provider selection and capability routing; specialist repositories stay independently installable.
- Provider backends require an explicit configuration, compatible hardware/runtime, health checks, and offline contract coverage before they appear as available capabilities.
- Remote provider modules stay disabled until the local app configuration opts in. A configured credential alone does not turn on remote Research or Voice dispatch.
- Any future code execution uses a dedicated, reviewed sandbox contract. A developer's Copilot sandbox setup is not silently reused as TARA's execution guarantee.

