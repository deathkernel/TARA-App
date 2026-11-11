# TARA-App — Feature & Neural-Network Diagrams

> **Accuracy note:** These diagrams are architecture documentation, not a claim that every feature is fully integrated or production-verified. Status is governed by [REMAINING_FEATURES.md](REMAINING_FEATURES.md) and [Project Status & Roadmap](PROJECT_STATUS_AND_ROADMAP.md). The neural-network internals below describe a generic Transformer model behind OmniRoute; TARA-App does not implement, train, own, or load those model weights.

## 1. Complete feature map

```mermaid
mindmap
  root((TARA-App))
    Core application
      Web UI and sessions
      Configuration and launchers
      Capability registry and router
      Orchestration and audit
      Model catalogue
    AI specialists
      Chat
      Code proposals
      Research
      Planner
      Creative
      Vision
      Model Hub
      Study
    Local intelligence and data
      Memory / SQLite
      CSV summaries
      Weather lookup
      Voice transcription
      Local read-aloud
    Actions and integrations
      Security policy
      Desktop allowlist
      Browser URL launch
      GitHub issue workflow
      MCP client and servers
      Skills loader
    Native and desktop
      Handler diagnostics
      Windows floating pet
    Safety controls
      Approval gates
      Timeouts and limits
      Fail-closed behavior
      Redacted audit
      No automatic merge
```

## 2. Capability routing and specialist dispatch

```mermaid
flowchart TD
  UI[Web UI / API / Floating Pet] --> Request[Validated request]
  Request --> Registry[Capability registry]
  Registry --> Router[Deterministic local router]
  Router --> Chat[tara_chat]
  Router --> Code[tara_code]
  Router --> Research[tara_research]
  Router --> Planner[tara_planner]
  Router --> Memory[tara_memory]
  Router --> Creative[tara_creative]
  Router --> Vision[tara_vision]
  Router --> Models[tara_models]
  Router --> Data[tara_data]
  Router --> Study[tara_study]
  Router --> Voice[tara_voice]
  Router --> Weather[tara_weather]
  Router --> Action[tara_action]
  Router --> Handler[TARA-Handler diagnostics]
  Action --> Sec[tara_security]
  Memory --> Sec
  Chat --> Result[Structured capability result]
  Code --> Result
  Research --> Result
  Planner --> Result
  Memory --> Result
  Creative --> Result
  Vision --> Result
  Models --> Result
  Data --> Result
  Study --> Result
  Voice --> Result
  Weather --> Result
  Action --> Result
  Handler --> Result
  Result --> Audit[Audit / response normalization]
  Audit --> UI
```

## 3. Chat, conversation history and memory

```mermaid
sequenceDiagram
  participant U as User
  participant UI as TARA UI
  participant C as Chat specialist
  participant M as Local memory
  participant O as OmniRoute
  U->>UI: Message and optional attachments
  UI->>C: Session + bounded history
  C->>M: Read relevant saved context (when enabled)
  M-->>C: Relevant memory snippets
  C->>O: Prompt + bounded context
  O-->>C: Model response
  C->>C: Validate and normalize response
  C-->>UI: Structured answer
  UI-->>U: Safe Markdown rendering
  Note over C,M: Memory writes/deletes require Security review and explicit approval
```

## 4. Code specialist — current and gated future

```mermaid
flowchart TD
  A[User coding task] --> B[Code specialist]
  B --> C[Analyze supplied request / source]
  C --> D[Proposal, plan or diff preview]
  D --> E[Human review]
  E --> F{Execution available and approved?}
  F -- No: current safe behavior --> G[Return proposal only]
  F -- Yes: future only --> H[Real OS/container sandbox]
  H --> I[Bounded test run]
  I --> J[Diff and test report]
  J --> K[Human-controlled promotion]
```

**Current limitation:** Code generation/planning is review-first. Workspace mutation and generated-code execution are blocked pending a real OS/container sandbox and security verification. No model-generated host shell commands.

## 5. Research and source review

```mermaid
flowchart LR
  Q[Research question] --> R[Research specialist]
  R --> X[Crossref public API]
  R --> W[Wikipedia public API]
  X --> S[Source records / links]
  W --> S
  S --> V[User reviews sources and excerpts]
```

## 6. Planner and bounded workflow engine

```mermaid
flowchart TD
  P[Task request] --> Plan[Build structured plan]
  Plan --> Validate[Validate schema, steps and dependencies]
  Validate --> Ready{Ready step?}
  Ready -- No --> Wait[Pending / blocked / complete]
  Ready -- Yes --> Gate{Approval required?}
  Gate -- Yes --> Approved{Valid one-step approval?}
  Approved -- No --> Pause[Pause for approval]
  Approved -- Yes --> Execute[Injected executor]
  Gate -- No --> Execute
  Execute --> Outcome{Step result}
  Outcome -- Success --> Validate
  Outcome -- Failure / denied --> Stop[Stop or mark remaining skipped]
  Wait --> Report[Workflow status report]
  Pause --> Report
  Stop --> Report
```

## 7. Security, permissions and audit

```mermaid
sequenceDiagram
  participant S as Specialist
  participant P as Permission policy
  participant A as Approval service / user
  participant L as Audit sink
  participant T as Tool adapter
  S->>P: Capability request
  P->>L: Persist policy decision
  alt Audit unavailable
    P-->>S: Fail closed
  else Approval needed
    P->>A: Request scoped approval
    A-->>P: Approve or deny
    P->>L: Record approval decision
    alt Approved
      P->>T: Dispatch allowlisted operation
      T-->>P: Structured result
    else Denied
      P-->>S: permission_denied
    end
  else Allowed read-only capability
    P->>T: Dispatch registered handler
    T-->>P: Structured result
  end
  P->>L: Record outcome and redacted error
  P-->>S: Result
```

## 8. Desktop actions and browser opening

```mermaid
flowchart TD
  U[User asks for local action] --> Parse[Recognize supported intent]
  Parse --> Policy[Security assessment]
  Policy --> Approval[One-operation approval]
  Approval --> Decision{Approved?}
  Decision -- No --> Deny[No action]
  Decision -- Yes --> Type{Allowlisted target?}
  Type -- Calculator / Notepad / Paint --> Fixed[Fixed executable + fixed argv]
  Type -- HTTP(S) URL --> Check[Validate scheme, host and URL]
  Check --> Browser[Delegate to system browser]
  Fixed --> Report[Bounded structured outcome]
  Browser --> Report
```

## 9. TARA-Handler native diagnostics and maintenance boundary

```mermaid
flowchart TB
  App[TARA-App Handler adapter] --> Bridge[Fixed argv subprocess boundary]
  Bridge --> Doctor[Read-only doctor / diagnostics]
  Doctor --> Inspect[System, components, dependencies and health]
  Inspect --> Result[Bounded diagnostic report]
  Result --> App
  Future[Other native maintenance capabilities] -.-> Guard[Policy / risk / transaction / backup / recovery]
  Guard -.-> Review[Explicitly reviewed and approved action]
  Note[Only the environment-diagnosis command is exposed by the current app integration]
```

## 10. Model Hub and OmniRoute model catalogue

```mermaid
sequenceDiagram
  participant UI as Model Hub UI
  participant T as tara_models
  participant O as OmniRoute
  participant P as Configured provider
  UI->>T: List / select / generate request
  T->>O: GET /v1/models
  O-->>T: Available route/model catalogue
  T-->>UI: Display configured catalogue
  UI->>T: Generation request
  T->>O: POST /v1/chat/completions
  O->>P: Route to configured model
  P-->>O: Generated response
  O-->>T: Response
  T-->>UI: Result and status
```

## 11. Generic neural network: Transformer inference

> **Conceptual model internals.** This is a generic decoder-only Transformer illustration. The actual architecture, layer count, attention variant, tokenizer, context size and weights depend on the model selected by the OmniRoute provider and are not discoverable from this repository's app code alone.

```mermaid
flowchart TB
  Text[Input text] --> Tok[Tokenizer]
  Tok --> IDs[Token IDs]
  IDs --> Emb[Token embeddings]
  Pos[Positional information] --> Emb
  Emb --> Block1[Transformer block 1]
  Block1 --> BlockN[... Transformer blocks N]
  BlockN --> Norm[Final normalization]
  Norm --> Head[Language-model head]
  Head --> Logits[Next-token scores / logits]
  Logits --> Sample[Decode / sample next token]
  Sample --> Output[Output token]
  Output -. autoregressive loop .-> Tok
```

## 12. Inside a generic Transformer block

```mermaid
flowchart TD
  X[Input hidden states] --> LN1[Normalization]
  LN1 --> QKV[Query / Key / Value projections]
  QKV --> Attn[Masked self-attention]
  Attn --> Add1[Residual connection]
  X --> Add1
  Add1 --> LN2[Normalization]
  LN2 --> MLP[Feed-forward network / MLP]
  MLP --> Add2[Residual connection]
  Add1 --> Add2
  Add2 --> Y[Output hidden states]
```

## 13. Attention mechanism — conceptual

```mermaid
flowchart LR
  X[Token representations] --> Q[Query projection]
  X --> K[Key projection]
  X --> V[Value projection]
  Q --> Score[Q × K transpose]
  K --> Score
  Score --> Mask[Apply causal mask]
  Mask --> Softmax[Softmax weights]
  Softmax --> Weighted[Weighted sum of values]
  V --> Weighted
  Weighted --> Out[Attention output projection]
```

## 14. Neural-network training versus TARA inference

```mermaid
flowchart TB
  subgraph Training[Model provider training pipeline — outside TARA]
    Data[Training data] --> Prep[Tokenize / prepare batches]
    Prep --> Forward[Forward pass]
    Forward --> Loss[Loss calculation]
    Loss --> Backprop[Backpropagation]
    Backprop --> Optimizer[Optimizer updates weights]
    Optimizer --> Weights[(Trained model weights)]
  end
  subgraph TARA[TARA runtime — inference client]
    Prompt[User prompt] --> Gateway[OmniRoute gateway]
    Gateway --> Model[Provider-hosted model]
    Model --> Answer[Generated tokens]
    Answer --> App[TARA validates and presents result]
  end
  Weights -. loaded/served by provider .-> Model
```

## 15. Vision, voice and multimodal paths

```mermaid
flowchart TD
  Image[User image] --> Vision[tara_vision]
  Vision --> OmniV[OmniRoute vision route]
  OmniV --> VResult[Image analysis response]
  Audio[User audio] --> Voice[tara_voice]
  Voice --> Local[Optional local faster-whisper]
  Local --> Transcript[Transcript text]
  Transcript --> Chat[Chat request]
  Chat --> Omni[OmniRoute chat route]
  Omni --> Reply[Text response]
  Reply --> ReadAloud[Browser local voice read-aloud]
```

## 16. Study, Data and Weather utilities

```mermaid
flowchart LR
  Notes[User notes / text PDF] --> Study[tara_study]
  Study --> StudyOut[Notes / fill-in quiz / flashcards / bounded plan]
  CSV[CSV attachment] --> Data[tara_data]
  Data --> Summary[Read-only CSV summary]
  Question[Weather question] --> Weather[tara_weather]
  Weather --> Geo[Open-Meteo geocoding]
  Geo --> Forecast[Open-Meteo forecast]
  Forecast --> WeatherOut[Forecast with attribution]
```

## 17. MCP tools and skills

```mermaid
flowchart TD
  User[User task] --> App[TARA app]
  App --> Skills[Skills loader]
  Skills --> Skill[Reviewed skill instructions]
  App --> MCP[MCP registry / client]
  MCP --> Config[Explicit server allowlist]
  Config --> Server[Configured stdio MCP server]
  Server --> Tools[Reviewed tools]
  Tools --> Gate[One-shot approval for tool calls]
  Gate --> Result[Structured tool result]
  Result --> App
  Note[Built-in time / scoped filesystem / Git read servers are optional and disabled by default]
```

## 18. Windows floating companion

```mermaid
flowchart LR
  Pet[Windows floating pet UI] --> Input[User submits message]
  Input --> Validate[Validate loopback URL and bounded history]
  Validate --> HTTP[POST local /api/chat]
  HTTP --> App[TARA local web app]
  App --> Chat[Chat capability]
  Chat --> Omni[OmniRoute, when configured]
  Omni --> Response[Response]
  Response --> Pet
  Pet -. no direct desktop action execution .-> Boundary[Local companion UI only]
```

## 19. Startup and deployment

```mermaid
flowchart TD
  Start[Developer / user] --> OS{Platform}
  OS --> Win[Windows launcher]
  OS --> Unix[macOS / Linux launcher]
  Win --> Env[Virtual environment and package install]
  Unix --> Env
  Env --> Config[Local config initialization]
  Config --> Optional[Optional Handler preparation]
  Optional --> App[Loopback TARA app]
  App --> UI[Web UI / optional Windows pet]
  App --> Omni[Configured local OmniRoute gateway]
  Omni --> Provider[Configured model providers]
```

## 20. Failure handling and fail-closed behavior

```mermaid
flowchart TD
  Req[Capability request] --> Validate[Validate schema, size and timeout]
  Validate --> Ready{Dependency and policy ready?}
  Ready -- No --> Fail[Return explicit failure; no side effect]
  Ready -- Yes --> Approval{Approval required?}
  Approval -- Yes --> Granted{Valid scoped approval?}
  Granted -- No --> Fail
  Granted -- Yes --> Run[Invoke registered handler]
  Approval -- No --> Run
  Run --> Valid{Valid bounded result?}
  Valid -- No --> Reject[Reject result and audit error]
  Valid -- Yes --> Audit[Audit outcome]
  Audit --> Return[Return structured response]
```

## Related authoritative project documents

- [Architecture](ARCHITECTURE.md)
- [Security model](SECURITY.md)
- [Remaining feature status](REMAINING_FEATURES.md)
- [Project history and roadmap](PROJECT_STATUS_AND_ROADMAP.md)
- [Integration contracts](INTEGRATION_CONTRACTS.md)
- [OmniRoute integration](OMNIROUTE_INTEGRATION.md)
- [Main README](../README.md)
