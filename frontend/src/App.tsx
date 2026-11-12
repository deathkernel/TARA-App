import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Approval = {
  id: string;
  description: string;
  expiresInSeconds?: number;
};

type Message = {
  role: "user" | "assistant";
  text: string;
  status?: string;
  hasAttachments?: boolean;
  approval?: Approval;
};

type Conversation = {
  id: string;
  title: string;
  updatedAt: number;
  messages: Message[];
};

type Attachment = {
  name: string;
  media_type: string;
  content_base64: string;
};

type SkillPack = {
  name: string;
  title: string;
  description: string;
  version: string;
  tags?: string[];
};

type ModelRoute = {
  specialist: string;
  model: string;
};

type ModelStatus = {
  status: string;
  provider?: string;
  service_available?: boolean;
  models?: ModelRoute[];
  error?: string;
};

type SpecialistHealth = {
  status: string;
  reason?: string;
};

type HealthStatus = {
  status?: string;
  specialists?: Record<string, SpecialistHealth>;
  model_gateway?: { status?: string; provider?: string };
};

type Integration = {
  id: string;
  name: string;
  category: string;
  description: string;
  cost: string;
  access: string;
  status: string;
  local: boolean;
  requirements: string[];
};

type IntegrationCatalogue = {
  status: string;
  automatic_install: boolean;
  write_tools_enabled: boolean;
  integrations: Integration[];
  summary?: { total: number; implemented: number; catalogue_only: number };
};

type McpStatus = {
  status: string;
  enabled_server_count?: number;
  audit_status?: string;
  servers?: Array<{ name: string; status?: string }>;
};

type ActivityItem = {
  id: string;
  time: number;
  label: string;
  detail: string;
  tone: "neutral" | "success" | "warning" | "danger";
};

type SendOptions = {
  history?: Message[];
};

const STORAGE_KEY = "tara-react-conversations";
const SESSION_KEY = "tara-react-session";
const MAX_FILES = 4;
const MAX_ATTACHMENT_BYTES = 10_000_000;
const FREE_MODELS_PROMPT = "List all available models";

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: "New session", updatedAt: Date.now(), messages: [] };
}

function readConversations(): Conversation[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is Conversation =>
      !!item && typeof item.id === "string" && typeof item.title === "string" &&
      Array.isArray(item.messages) && item.messages.every((message: unknown) =>
        !!message && typeof message === "object" && "text" in message &&
        typeof message.text === "string" && "role" in message &&
        (message.role === "user" || message.role === "assistant"))
    ).slice(0, 30);
  } catch {
    return [];
  }
}

function errorText(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string") {
    return payload.error;
  }
  return fallback;
}

function answerText(payload: any): string {
  const candidates = [
    payload?.result?.data?.text,
    payload?.result?.data?.reply,
    payload?.result?.data?.answer,
    payload?.result?.error,
    payload?.result?.data?.message,
    payload?.error,
  ];
  const found = candidates.find((value) => typeof value === "string" && value.trim());
  return found ?? JSON.stringify(payload, null, 2);
}

function approvalFromPayload(payload: any): Approval | undefined {
  if (payload?.status !== "approval_required") return undefined;
  const data = payload?.result?.data;
  if (!data || typeof data.approval_id !== "string") return undefined;
  return {
    id: data.approval_id,
    description: typeof data.approval_description === "string"
      ? data.approval_description
      : "TARA-Security is requesting approval for this operation.",
    expiresInSeconds: typeof data.expires_in_seconds === "number" ? data.expires_in_seconds : undefined,
  };
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorText(payload, "Request failed (" + response.status + ")"));
  return payload as T;
}

function mediaTypeForFile(file: File): string {
  if (file.type) return file.type;
  const extension = file.name.toLowerCase().split(".").pop() ?? "";
  const known: Record<string, string> = {
    csv: "text/csv", txt: "text/plain", md: "text/markdown", pdf: "application/pdf",
    mp3: "audio/mpeg", wav: "audio/wav", m4a: "audio/mp4", mp4: "audio/mp4",
    webm: "audio/webm", ogg: "audio/ogg", flac: "audio/flac", aac: "audio/aac",
  };
  return known[extension] ?? "application/octet-stream";
}

function fileToAttachment(file: File): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read " + file.name));
    reader.onload = () => {
      const encoded = String(reader.result).split(",", 2)[1] ?? "";
      resolve({
        name: file.name,
        media_type: mediaTypeForFile(file),
        content_base64: encoded,
      });
    };
    reader.readAsDataURL(file);
  });
}

function statusLabel(status?: string): string {
  if (!status) return "Unknown";
  return status.replaceAll("_", " ");
}

function timeLabel(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const existing = readConversations();
    return existing.length ? existing : [newConversation()];
  });
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) ?? "");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [approvalBusy, setApprovalBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectedSkill, setSelectedSkill] = useState("");
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [skills, setSkills] = useState<SkillPack[]>([]);
  const [catalogue, setCatalogue] = useState<IntegrationCatalogue | null>(null);
  const [mcpStatus, setMcpStatus] = useState<McpStatus | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<"status" | "models" | "integrations">("status");
  const [activityOpen, setActivityOpen] = useState(false);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [viewMode, setViewMode] = useState<"normal" | "compact">("normal");

  const active = useMemo(
    () => conversations.find((item) => item.id === sessionId) ?? conversations[0],
    [conversations, sessionId],
  );

  const visibleConversations = useMemo(() => {
    const term = search.trim().toLowerCase();
    return conversations
      .slice()
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .filter((item) => !term || item.title.toLowerCase().includes(term));
  }, [conversations, search]);

  function logActivity(label: string, detail: string, tone: ActivityItem["tone"] = "neutral") {
    setActivity((items) => [
      ...items.slice(-39),
      { id: crypto.randomUUID(), time: Date.now(), label, detail, tone },
    ]);
  }

  function updateActive(transform: (conversation: Conversation) => Conversation) {
    if (!active) return;
    setConversations((items) => items.map((item) => item.id === active.id ? transform(item) : item));
  }

  async function refreshWorkspace() {
    const [healthResult, modelsResult, skillsResult, catalogueResult, mcpResult] = await Promise.allSettled([
      api<HealthStatus>("/api/health"),
      api<ModelStatus>("/api/models"),
      api<{ skills?: SkillPack[] }>("/api/skills"),
      api<IntegrationCatalogue>("/api/mcp/catalogue"),
      api<McpStatus>("/api/mcp/status"),
    ]);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    if (modelsResult.status === "fulfilled") setModelStatus(modelsResult.value);
    if (skillsResult.status === "fulfilled") setSkills(skillsResult.value.skills ?? []);
    if (catalogueResult.status === "fulfilled") setCatalogue(catalogueResult.value);
    if (mcpResult.status === "fulfilled") setMcpStatus(mcpResult.value);
    if (healthResult.status === "fulfilled" || modelsResult.status === "fulfilled") {
      logActivity("Workspace status refreshed", "Local specialist and gateway status checked.", "success");
    }
  }

  useEffect(() => {
    void refreshWorkspace();
  }, []);

  useEffect(() => {
    if (!conversations.length) return;
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([...conversations].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 30)),
    );
  }, [conversations]);

  useEffect(() => {
    if (!active) return;
    if (active.id !== sessionId) setSessionId(active.id);
    localStorage.setItem(SESSION_KEY, active.id);
  }, [active, sessionId]);

  function startNewSession() {
    const item = newConversation();
    setConversations((items) => [item, ...items].slice(0, 30));
    setSessionId(item.id);
    setDraft("");
    setSelectedFiles([]);
    setEditingIndex(null);
    setNotice("");
    setMobileSidebarOpen(false);
    logActivity("New session created", "A fresh local conversation is ready.");
  }

  function selectSpecialist(name: string, prompt: string) {
    setDraft(prompt);
    setSelectedSkill("");
    setMobileSidebarOpen(false);
    logActivity(name + " workspace selected", "A task starter was added to the composer.");
    document.getElementById("message-composer")?.focus();
  }

  function handleFiles(fileList: FileList | null) {
    if (!fileList?.length) return;
    const incoming = Array.from(fileList);
    const combined = [...selectedFiles, ...incoming];
    const totalBytes = combined.reduce((sum, file) => sum + file.size, 0);
    if (combined.length > MAX_FILES) {
      setNotice("Attach up to four files per message.");
      return;
    }
    if (totalBytes > MAX_ATTACHMENT_BYTES) {
      setNotice("Combined attachments must stay within 10 MB per message.");
      return;
    }
    setSelectedFiles(combined);
    setNotice("");
    logActivity("Files attached", incoming.map((file) => file.name).join(", "));
  }

  async function sendMessage(
    textOverride?: string,
    fileOverride?: File[],
    options: SendOptions = {},
  ) {
    const question = (textOverride ?? draft).trim() || (fileOverride?.length || selectedFiles.length
      ? "Please inspect and help me with the attached files."
      : "");
    const files = fileOverride ?? selectedFiles;
    if ((!question && files.length === 0) || sending || !active) return;

    const historyMessages = options.history ?? (
      editingIndex !== null ? active.messages.slice(0, editingIndex) : active.messages
    );
    const history = historyMessages.slice(-20).map(({ role, text }) => ({ role, content: text }));
    const userMessage: Message = { role: "user", text: question, hasAttachments: files.length > 0 };
    updateActive((item) => ({
      ...item,
      title: item.title === "New session"
        ? question.replace(/\s+/g, " ").slice(0, 52)
        : item.title,
      updatedAt: Date.now(),
      messages: [...historyMessages, userMessage].slice(-60),
    }));

    setDraft("");
    setSelectedFiles([]);
    setEditingIndex(null);
    setSending(true);
    setNotice("");
    logActivity("Request sent", question.slice(0, 120), "neutral");

    try {
      const attachments = await Promise.all(files.map(fileToAttachment));
      const payload = await api<any>("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          question,
          session_id: active.id,
          attachments,
          history,
          ...(selectedSkill ? { skill: selectedSkill } : {}),
        }),
      });
      const approval = approvalFromPayload(payload);
      const text = approval
        ? "TARA-Security reviewed this request. Nothing has run yet. Review the operation and approve it explicitly if you want to continue."
        : answerText(payload);
      const assistantMessage: Message = {
        role: "assistant",
        text,
        status: payload?.status ?? "success",
        ...(approval ? { approval } : {}),
      };
      updateActive((item) => ({
        ...item,
        updatedAt: Date.now(),
        messages: [...item.messages, assistantMessage].slice(-60),
      }));
      logActivity(
        approval ? "Approval required" : "Response received",
        approval ? approval.description : "The specialist returned a response.",
        approval ? "warning" : "success",
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Local server unavailable.";
      updateActive((item) => ({
        ...item,
        updatedAt: Date.now(),
        messages: [...item.messages, { role: "assistant", text: message, status: "unavailable" }].slice(-60),
      }));
      setNotice(message);
      logActivity("Request failed", message, "danger");
    } finally {
      setSending(false);
    }
  }

  async function actOnApproval(approval: Approval, action: "approve" | "cancel") {
    if (!active || approvalBusy) return;
    setApprovalBusy(approval.id);
    try {
      const payload = await api<any>(action === "approve" ? "/api/approve" : "/api/cancel", {
        method: "POST",
        body: JSON.stringify({ approval_id: approval.id, session_id: active.id }),
      });
      const nextApproval = approvalFromPayload(payload);
      const responseText = nextApproval
        ? "Approval is still required for this operation."
        : answerText(payload);
      updateActive((item) => ({
        ...item,
        updatedAt: Date.now(),
        messages: item.messages.map((message) => message.approval?.id === approval.id
          ? {
              ...message,
              text: responseText,
              status: payload?.status ?? (action === "approve" ? "completed" : "cancelled"),
              ...(nextApproval ? { approval: nextApproval } : { approval: undefined }),
            }
          : message),
      }));
      logActivity(
        action === "approve" ? "Approval submitted" : "Approval cancelled",
        approval.description,
        action === "approve" ? "success" : "warning",
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Approval request failed.";
      setNotice(message);
      logActivity("Approval action failed", message, "danger");
    } finally {
      setApprovalBusy("");
    }
  }

  function readAloud(text: string) {
    if (typeof window.speechSynthesis === "undefined") {
      setNotice("Local read-aloud is not available in this browser.");
      return;
    }
    const voices = window.speechSynthesis.getVoices().filter((voice) => voice.localService);
    if (!voices.length) {
      setNotice("No installed local speech voice is available on this device.");
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text.slice(0, 5000));
    const language = navigator.language.toLowerCase();
    utterance.voice = voices.find((voice) => voice.lang.toLowerCase().startsWith(language)) ?? voices[0];
    utterance.lang = utterance.voice.lang;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    logActivity("Local read-aloud started", "Using an installed browser voice; no audio was sent to OmniRoute.");
  }

  function startEditing(index: number, message: Message) {
    if (message.role !== "user" || message.hasAttachments) return;
    setEditingIndex(index);
    setDraft(message.text);
    setNotice("");
    document.getElementById("message-composer")?.focus();
  }

  function regenerateAnswer(index: number) {
    if (!active || sending || index < 1) return;
    const previous = active.messages[index - 1];
    if (previous?.role !== "user" || previous.hasAttachments) return;
    const history = active.messages.slice(0, index - 1);
    void sendMessage(previous.text, [], { history });
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
    if (event.key === "Escape" && editingIndex !== null) {
      setEditingIndex(null);
      setDraft("");
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void sendMessage();
  }

  async function refreshModels() {
    try {
      setModelStatus(await api<ModelStatus>("/api/models"));
      logActivity("Model catalogue refreshed", "OmniRoute model availability checked.", "success");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not read model status.");
    }
  }

  async function refreshIntegrations() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    try {
      const [nextCatalogue, nextStatus] = await Promise.all([
        api<IntegrationCatalogue>("/api/mcp/catalogue", { signal: controller.signal }),
        api<McpStatus>("/api/mcp/status", { signal: controller.signal }),
      ]);
      setCatalogue(nextCatalogue);
      setMcpStatus(nextStatus);
      logActivity("Integration catalogue refreshed", "Read-only integration metadata loaded.", "success");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not refresh integrations.");
    } finally {
      window.clearTimeout(timeout);
    }
  }

  const gatewayStatus = health?.model_gateway?.status ?? "checking";
  const chatStatus = health?.specialists?.chat?.status ?? "checking";

  return (
    <div className={"app-shell" + (mobileSidebarOpen ? " sidebar-open" : "")}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">T</span>
          <div><strong>TARA</strong><span>DEVELOPER WORKSPACE</span></div>
          <button className="sidebar-collapse" type="button" onClick={() => setMobileSidebarOpen(false)} aria-label="Close sidebar">×</button>
        </div>

        <button className="new-session" type="button" onClick={startNewSession}>
          <span>＋</span> New session <kbd>Ctrl N</kbd>
        </button>

        <div className="sidebar-section">
          <div className="section-heading"><span>WORKSPACES</span><span className="section-count">04</span></div>
          <button className="nav-item selected" type="button" onClick={() => selectSpecialist("Chat", "")}>
            <span className="nav-icon">◉</span><span>Chat</span><span className="nav-state">●</span>
          </button>
          <button className="nav-item" type="button" onClick={() => selectSpecialist("Code", "Help me inspect this code, identify the problem, and propose a safe, reviewable fix. Do not execute commands or modify files.")}>
            <span className="nav-icon">⌘</span><span>Code tasks</span>
          </button>
          <button className="nav-item" type="button" onClick={() => selectSpecialist("Research", "Research this topic using reliable sources, compare the evidence, and provide links.")}>
            <span className="nav-icon">⌕</span><span>Research</span>
          </button>
          <button className="nav-item" type="button" onClick={() => selectSpecialist("Study", "Create source-grounded study notes from the attached material. Clearly identify anything not supported by the source.")}>
            <span className="nav-icon">▤</span><span>Study</span>
          </button>
        </div>

        <div className="session-heading">
          <div className="section-heading"><span>SESSIONS</span><span className="section-count">{visibleConversations.length.toString().padStart(2, "0")}</span></div>
          <label className="session-search">
            <span>⌕</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a session" aria-label="Find a session" />
          </label>
        </div>
        <nav className="conversation-list" aria-label="Recent sessions">
          {visibleConversations.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === active?.id ? "conversation active" : "conversation"}
              onClick={() => { setSessionId(item.id); setMobileSidebarOpen(false); }}
            >
              <span className="conversation-dot" />
              <span className="conversation-title">{item.title}</span>
              <span className="conversation-time">{timeLabel(item.updatedAt)}</span>
            </button>
          ))}
          {!visibleConversations.length && <p className="empty-sessions">No matching sessions.</p>}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-runtime">
            <span className={gatewayStatus === "healthy" ? "runtime-dot online" : "runtime-dot"} />
            <div><strong>OmniRoute</strong><span>{statusLabel(gatewayStatus)}</span></div>
            <button type="button" onClick={() => void refreshWorkspace()} aria-label="Refresh workspace status">↻</button>
          </div>
          <div className="profile-row"><span className="profile-avatar">T</span><div><strong>TARA Local</strong><span>Personal workspace</span></div><span className="profile-menu">•••</span></div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" type="button" onClick={() => setMobileSidebarOpen(true)} aria-label="Open sidebar">☰</button>
            <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-separator">/</span><strong>{active?.title ?? "New session"}</strong></div>
            <span className="session-state"><i /> {sending ? "Working" : "Ready"}</span>
          </div>
          <div className="topbar-actions">
            <button className="toolbar-button" type="button" onClick={() => setActivityOpen((open) => !open)} aria-expanded={activityOpen}>▤ <span>Activity</span></button>
            <button className="toolbar-button" type="button" onClick={() => setInspectorOpen((open) => !open)} aria-expanded={inspectorOpen}>☷ <span>Inspector</span></button>
            <button className="toolbar-button icon-only" type="button" onClick={() => void refreshWorkspace()} aria-label="Refresh status">↻</button>
          </div>
        </header>

        <div className="session-toolbar">
          <div className="session-tabs">
            <span className="session-tab active"><span>◉</span> Conversation</span>
            <span className="session-tab muted-tab"><span>⌘</span> Code review <small>SAFE MODE</small></span>
          </div>
          <div className="session-tools">
            <span className="mode-indicator"><i /> Review-first</span>
            <button type="button" className="view-mode" onClick={() => setViewMode((mode) => mode === "normal" ? "compact" : "normal")}>
              {viewMode === "normal" ? "Normal view" : "Compact view"} ▾
            </button>
          </div>
        </div>

        {notice && <div className="notice" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label="Dismiss notice">×</button></div>}

        <section className={"chat-area" + (viewMode === "compact" ? " compact-view" : "")} aria-label="Conversation">
          {!active?.messages.length && (
            <div className="welcome">
              <div className="welcome-eyebrow"><span className="welcome-spark">✳</span> YOUR LOCAL AI WORKSPACE</div>
              <h1>What are we <em>building</em> today?</h1>
              <p>One workspace for thinking, coding, research and learning. TARA routes each request to the right specialist through OmniRoute.</p>
              <div className="starter-grid">
                <button type="button" onClick={() => selectSpecialist("Code", "Review this code and propose a safe fix. Explain the root cause and include tests. Do not execute commands or modify files.")}>
                  <span className="starter-icon code-icon">⌘</span><span><strong>Build with Code</strong><small>Debug, review and plan changes</small></span><b>↗</b>
                </button>
                <button type="button" onClick={() => selectSpecialist("Research", "Research this topic with reliable sources and explain the evidence.")}>
                  <span className="starter-icon research-icon">⌕</span><span><strong>Research a topic</strong><small>Find sources and compare evidence</small></span><b>↗</b>
                </button>
                <button type="button" onClick={() => selectSpecialist("Study", "Make concise, source-grounded study notes from my attached file.")}>
                  <span className="starter-icon study-icon">▤</span><span><strong>Study smarter</strong><small>Notes, quizzes and flashcards</small></span><b>↗</b>
                </button>
                <button type="button" onClick={() => void sendMessage(FREE_MODELS_PROMPT, [])}>
                  <span className="starter-icon model-icon">◈</span><span><strong>Explore models</strong><small>See routes exposed by OmniRoute</small></span><b>↗</b>
                </button>
              </div>
              <div className="welcome-footnote"><span>✦</span> Your data stays in your local app; model prompts may be sent to providers configured in OmniRoute.</div>
            </div>
          )}

          <div className="messages">
            {(active?.messages ?? []).map((message, index) => (
              <article key={active?.id + "-" + index} className={"message " + message.role}>
                <div className="message-avatar">{message.role === "user" ? "Y" : "T"}</div>
                <div className="message-content">
                  <div className="message-heading">
                    <strong>{message.role === "user" ? "You" : "TARA"}</strong>
                    {message.status && message.status !== "success" && <span className={"message-status " + message.status}>{statusLabel(message.status)}</span>}
                    {message.hasAttachments && <span className="attachment-tag">ATTACHMENTS</span>}
                    <div className="message-actions">
                      {message.role === "user" && !message.hasAttachments && <button type="button" onClick={() => startEditing(index, message)} disabled={sending}>Edit</button>}
                      {message.role === "assistant" && index > 0 && <button type="button" onClick={() => regenerateAnswer(index)} disabled={sending}>Regenerate</button>}
                      {message.role === "assistant" && <button type="button" onClick={() => readAloud(message.text)}>Read aloud</button>}
                      <button type="button" onClick={() => void navigator.clipboard?.writeText(message.text)} aria-label="Copy message">Copy</button>
                    </div>
                  </div>
                  <div className={message.role === "assistant" ? "message-body markdown-body" : "message-body user-body"}>
                    {message.role === "assistant"
                      ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
                      : message.text}
                  </div>
                  {message.approval && (
                    <div className="approval-card">
                      <div className="approval-heading"><span>⚑</span><strong>Security approval required</strong><span className="approval-expiry">{message.approval.expiresInSeconds ?? 120}s</span></div>
                      <p>{message.approval.description}</p>
                      <div className="approval-note">Nothing runs until you approve this exact operation. Approval is one-time and expires.</div>
                      <div className="approval-actions">
                        <button type="button" className="approve-button" onClick={() => void actOnApproval(message.approval!, "approve")} disabled={approvalBusy === message.approval.id}>
                          {approvalBusy === message.approval.id ? "Processing…" : "Approve once"}
                        </button>
                        <button type="button" className="cancel-button" onClick={() => void actOnApproval(message.approval!, "cancel")} disabled={approvalBusy === message.approval.id}>Cancel</button>
                      </div>
                    </div>
                  )}
                </div>
              </article>
            ))}
            {sending && <div className="working-indicator"><span className="working-pulse" /><span>TARA is working on your request…</span></div>}
          </div>
        </section>

        {activityOpen && (
          <section className="activity-panel">
            <div className="activity-header"><div><strong>Session activity</strong><span>Local request lifecycle · no shell commands are run here</span></div><button type="button" onClick={() => setActivityOpen(false)} aria-label="Close activity">×</button></div>
            <div className="activity-list">
              {activity.slice().reverse().map((item) => (
                <div className="activity-row" key={item.id}>
                  <span className={"activity-dot " + item.tone} />
                  <strong>{item.label}</strong><span>{item.detail}</span><time>{timeLabel(item.time)}</time>
                </div>
              ))}
              {!activity.length && <p className="empty-state">Activity will appear here when you use TARA.</p>}
            </div>
          </section>
        )}

        <form className="composer" onSubmit={submit}>
          {editingIndex !== null && (
            <div className="edit-banner"><span>Editing your message</span><button type="button" onClick={() => { setEditingIndex(null); setDraft(""); }}>Cancel edit</button></div>
          )}
          {selectedFiles.length > 0 && (
            <div className="file-chips">
              {selectedFiles.map((file, index) => (
                <span className="file-chip" key={file.name + "-" + index}><span>▧</span>{file.name}<button type="button" onClick={() => setSelectedFiles((items) => items.filter((_, itemIndex) => itemIndex !== index))} aria-label={"Remove " + file.name}>×</button></span>
              ))}
            </div>
          )}
          <div className="composer-main">
            <label className="attach-button" title="Attach files">
              <input type="file" multiple hidden onChange={(event) => { handleFiles(event.target.files); event.target.value = ""; }} />
              ＋
            </label>
            <textarea
              id="message-composer"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder="Ask TARA to explain, build, debug or research…"
              aria-label="Message TARA"
              rows={1}
              maxLength={20000}
            />
            <button className="send-button" type="submit" disabled={sending || (!draft.trim() && !selectedFiles.length)} aria-label="Send message">
              {sending ? <span className="send-spinner" /> : "↑"}
            </button>
          </div>
          <div className="composer-footer">
            <label className="skill-picker"><span>Skill</span>
              <select value={selectedSkill} onChange={(event) => setSelectedSkill(event.target.value)} aria-label="Select a skill">
                <option value="">Auto select</option>
                {skills.map((skill) => <option key={skill.name} value={skill.name}>{skill.title}</option>)}
              </select>
            </label>
            <span className="composer-hint">Enter to send · Shift + Enter for new line</span>
            <span className="privacy-hint">OmniRoute may send prompts to configured providers</span>
          </div>
        </form>
        <footer className="workspace-footer"><span>●</span> TARA is in review-first mode <span className="footer-divider">·</span> Code execution is disabled until a real OS sandbox is available</footer>
      </main>

      {inspectorOpen && (
        <aside className="inspector">
          <div className="inspector-header"><div><span className="inspector-kicker">SESSION CONTEXT</span><strong>Inspector</strong></div><button type="button" onClick={() => setInspectorOpen(false)} aria-label="Close inspector">×</button></div>
          <div className="inspector-tabs">
            <button type="button" className={inspectorTab === "status" ? "active" : ""} onClick={() => setInspectorTab("status")}>Status</button>
            <button type="button" className={inspectorTab === "models" ? "active" : ""} onClick={() => setInspectorTab("models")}>Models</button>
            <button type="button" className={inspectorTab === "integrations" ? "active" : ""} onClick={() => setInspectorTab("integrations")}>Tools</button>
          </div>

          {inspectorTab === "status" && (
            <div className="inspector-content">
              <section className="inspector-card">
                <div className="card-title"><strong>Runtime health</strong><span className={gatewayStatus === "healthy" ? "health-pill healthy" : "health-pill"}>{statusLabel(gatewayStatus)}</span></div>
                <p>Inference gateway</p><div className="runtime-detail"><span>OmniRoute</span><strong>{statusLabel(gatewayStatus)}</strong></div>
                <div className="runtime-detail"><span>Chat specialist</span><strong>{statusLabel(chatStatus)}</strong></div>
              </section>
              <section className="inspector-card">
                <div className="card-title"><strong>Specialists</strong><span>{Object.keys(health?.specialists ?? {}).length} registered</span></div>
                {Object.entries(health?.specialists ?? {}).map(([name, item]) => (
                  <div className="specialist-row" key={name}><span className="specialist-icon">{name.slice(0, 1).toUpperCase()}</span><span>{name}</span><b className={item.status === "healthy" ? "text-success" : "text-muted"}>{statusLabel(item.status)}</b></div>
                ))}
                {!health?.specialists && <p className="empty-state">Checking specialist health…</p>}
              </section>
              <section className="inspector-card">
                <div className="card-title"><strong>Security posture</strong><span className="health-pill healthy">Protected</span></div>
                <ul className="security-list"><li>Review-first code workflow</li><li>One-time scoped approvals</li><li>Durable MCP audit trail</li><li>No host-shell execution</li></ul>
              </section>
              <section className="inspector-card terminal-locked">
                <div className="card-title"><strong>Terminal</strong><span className="health-pill locked">Locked</span></div>
                <div className="terminal-preview"><span>tara@local:~$</span> <i>command execution unavailable</i></div>
                <p>Terminal execution stays disabled until an OS-level sandbox and isolation tests are in place.</p>
              </section>
            </div>
          )}

          {inspectorTab === "models" && (
            <div className="inspector-content">
              <section className="inspector-card">
                <div className="card-title"><strong>OmniRoute models</strong><button type="button" className="text-button" onClick={() => void refreshModels()}>Refresh</button></div>
                <p>Routes and provider lifecycle are managed by OmniRoute.</p>
                {(modelStatus?.models ?? []).map((model) => (
                  <div className="model-row" key={model.specialist + model.model}><span><strong>{model.specialist}</strong><small>{model.model}</small></span><b>Route</b></div>
                ))}
                {modelStatus?.status !== "available" && <p className="empty-state">{modelStatus?.error ?? "Model catalogue is managed externally or unavailable."}</p>}
                <button type="button" className="wide-secondary" onClick={() => { setDraft(FREE_MODELS_PROMPT); document.getElementById("message-composer")?.focus(); }}>Ask TARA to list models</button>
              </section>
            </div>
          )}

          {inspectorTab === "integrations" && (
            <div className="inspector-content">
              <section className="inspector-card">
                <div className="card-title"><strong>MCP integrations</strong><button type="button" className="text-button" onClick={() => void refreshIntegrations()}>Refresh</button></div>
                <p>Free-first catalogue. Discovery never installs or enables a server.</p>
                <div className="integration-summary">
                  <div><strong>{catalogue?.summary?.implemented ?? 0}</strong><span>Available</span></div>
                  <div><strong>{catalogue?.summary?.catalogue_only ?? 0}</strong><span>Catalogue</span></div>
                  <div><strong>{mcpStatus?.enabled_server_count ?? 0}</strong><span>Enabled</span></div>
                </div>
                {(catalogue?.integrations ?? []).map((integration) => (
                  <div className="integration-row" key={integration.id}>
                    <div className="integration-row-top"><strong>{integration.name}</strong><span className={integration.status === "implemented" ? "integration-state ready" : "integration-state"}>{integration.status === "implemented" ? "Available" : "Planned"}</span></div>
                    <p>{integration.description}</p>
                    <small>{integration.access} · {integration.cost}</small>
                  </div>
                ))}
                <p className="security-footnote">No automatic installation, credential setup or write-tool activation. Every integration requires separate review.</p>
              </section>
            </div>
          )}
          <div className="inspector-footer"><span>Local app</span><span>API v1.0</span></div>
        </aside>
      )}
    </div>
  );
}
