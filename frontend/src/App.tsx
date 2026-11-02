import { ChangeEvent, FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ApprovalData = {
  approval_id: string;
  approval_description: string;
  intended_module?: string;
  intended_action?: string;
};

type Message = {
  role: "user" | "assistant";
  text: string;
  status?: string;
  approval?: ApprovalData;
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
  data_base64: string;
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
  pull?: { status?: string; model?: string; message?: string };
};

type DiagnosticsData = {
  timestamp: number;
  overall_status: string;
  environment: { platform: string; python_version: string; pid: number };
  hardware: {
    memory: { supported: boolean; total_gb: number; available_gb: number; used_gb: number; load_percent: number };
    cpu: { supported: boolean; cpu_percent: number };
    disk: { supported: boolean; total_gb: number; free_gb: number; percent_used: number };
  };
  omniroute: { status: string; base_url: string; message?: string; models_available?: number };
  specialists: Record<string, { status: string; capabilities: string[] }>;
  storage: { workspace: string; session_db?: { exists: boolean; size_bytes: number }; audit_log?: { exists: boolean; size_bytes: number } };
  issues: Array<{ severity: string; component: string; message: string; recommendation: string }>;
};

const STORAGE_KEY = "tara-react-conversations";
const SESSION_KEY = "tara-react-session";
const FREE_MODELS_PROMPT = "List all available models";

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: "New chat", updatedAt: Date.now(), messages: [] };
}

function readConversations(): Conversation[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is Conversation =>
      !!item && typeof item.id === "string" && typeof item.title === "string" &&
      Array.isArray(item.messages) && item.messages.every((m: unknown) =>
        !!m && typeof m === "object" && "text" in m && typeof m.text === "string" &&
        "role" in m && (m.role === "user" || m.role === "assistant"))
    ).slice(0, 24);
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
    payload?.result?.data?.output,
    payload?.result?.data?.answer,
    payload?.result?.error,
    payload?.result?.data?.message,
    payload?.error,
  ];
  const found = candidates.find((value) => typeof value === "string" && value.trim());
  return found ?? JSON.stringify(payload, null, 2);
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorText(payload, `Request failed (${response.status})`));
  return payload as T;
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const existing = readConversations();
    return existing.length ? existing : [newConversation()];
  });
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) ?? "");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [modelsOpen, setModelsOpen] = useState(false);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [modelBusy, setModelBusy] = useState("");
  const [diagOpen, setDiagOpen] = useState(false);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsData | null>(null);
  const [diagBusy, setDiagBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const active = useMemo(() => conversations.find((item) => item.id === sessionId) ?? conversations[0], [conversations, sessionId]);

  // Reconcile with server SQLite sessions on mount
  useEffect(() => {
    async function syncServerSessions() {
      try {
        const res = await api<{ status: string; sessions: Array<{ session_id: string; created_at: number; message_count: number }> }>("/api/sessions");
        if (res && res.status === "success" && Array.isArray(res.sessions) && res.sessions.length > 0) {
          setConversations((localList) => {
            const map = new Map(localList.map((c) => [c.id, c]));
            for (const s of res.sessions) {
              if (!map.has(s.session_id)) {
                map.set(s.session_id, {
                  id: s.session_id,
                  title: "Saved chat",
                  updatedAt: (s.created_at || Date.now() / 1000) * 1000,
                  messages: [],
                });
              }
            }
            return Array.from(map.values()).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 24);
          });
        }
      } catch {
        // Fall back gracefully to localStorage
      }
    }
    void syncServerSessions();
  }, []);

  useEffect(() => {
    if (!conversations.length) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...conversations].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 24)));
  }, [conversations]);

  useEffect(() => {
    if (!active) return;
    if (active.id !== sessionId) setSessionId(active.id);
    localStorage.setItem(SESSION_KEY, active.id);
  }, [active, sessionId]);

  async function refreshModels() {
    setModelBusy("refresh");
    try {
      setModelStatus(await api<ModelStatus>("/api/models"));
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not read OmniRoute model status.");
    } finally {
      setModelBusy("");
    }
  }

  async function refreshDiagnostics() {
    setDiagBusy(true);
    try {
      const res = await api<{ status: string; diagnostics: DiagnosticsData }>("/api/system/diagnostics");
      if (res && res.status === "success") {
        setDiagnostics(res.diagnostics);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not read system diagnostics.");
    } finally {
      setDiagBusy(false);
    }
  }

  useEffect(() => {
    if (modelsOpen && !modelStatus) void refreshModels();
  }, [modelsOpen]);

  useEffect(() => {
    if (diagOpen) void refreshDiagnostics();
  }, [diagOpen]);

  function updateActive(transform: (conversation: Conversation) => Conversation) {
    if (!active) return;
    setConversations((items) => items.map((item) => (item.id === active.id ? transform(item) : item)));
  }

  async function startNewChat() {
    const item = newConversation();
    try {
      await api("/api/sessions/new", {
        method: "POST",
        body: JSON.stringify({ session_id: item.id, metadata: { title: item.title } }),
      });
    } catch {
      // Offline fallback
    }
    setConversations((items) => [item, ...items].slice(0, 24));
    setSessionId(item.id);
    setDraft("");
    setAttachments([]);
    setNotice("");
  }

  async function deleteChat(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await api(`/api/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }).catch(() =>
        api("/api/sessions/delete", { method: "POST", body: JSON.stringify({ session_id: id }) })
      );
    } catch {
      // Offline fallback
    }
    setConversations((items) => {
      const remaining = items.filter((i) => i.id !== id);
      if (!remaining.length) {
        const fresh = newConversation();
        setSessionId(fresh.id);
        return [fresh];
      }
      if (sessionId === id) {
        setSessionId(remaining[0].id);
      }
      return remaining;
    });
  }

  function handleFileSelected(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files || !files.length) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.size > 8 * 1024 * 1024) {
        setNotice(`File ${file.name} exceeds the 8MB limit.`);
        continue;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        const base64Data = result.includes(",") ? result.split(",")[1] : result;
        setAttachments((prev) => [
          ...prev,
          {
            name: file.name,
            media_type: file.type || "application/octet-stream",
            data_base64: base64Data,
          },
        ]);
      };
      reader.readAsDataURL(file);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  }

  async function sendMessage(textOverride?: string) {
    const question = (textOverride ?? draft).trim();
    if (!question || sending || !active) return;
    const history = active.messages.slice(-20).map(({ role, text }) => ({ role, content: text }));
    const currentAttachments = [...attachments];
    const userMessage: Message = { role: "user", text: question };

    updateActive((item) => ({
      ...item,
      title: item.title === "New chat" ? question.replace(/\s+/g, " ").slice(0, 48) : item.title,
      updatedAt: Date.now(),
      messages: [...item.messages, userMessage].slice(-24),
    }));
    setDraft("");
    setAttachments([]);
    setSending(true);
    setNotice("");

    try {
      const payload = await api<any>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ question, session_id: active.id, attachments: currentAttachments, history }),
      });

      const approvalId = payload?.result?.data?.approval_id;
      const approvalDesc = payload?.result?.data?.approval_description;
      const isApproval = payload?.status === "approval_required" && typeof approvalId === "string";

      const text = isApproval
        ? "TARA-Security assessed this operation. Review the details below to approve or cancel:"
        : answerText(payload);

      const assistantMessage: Message = {
        role: "assistant",
        text,
        status: payload?.status ?? "success",
        approval: isApproval
          ? {
              approval_id: approvalId,
              approval_description: approvalDesc || "Run the requested operation once?",
              intended_module: payload?.route?.intended_module,
              intended_action: payload?.route?.intended_action,
            }
          : undefined,
      };

      updateActive((item) => ({
        ...item,
        updatedAt: Date.now(),
        messages: [...item.messages, assistantMessage].slice(-24),
      }));
    } catch (error) {
      const failureMessage: Message = {
        role: "assistant",
        text: error instanceof Error ? error.message : "Local server unavailable.",
        status: "unavailable",
      };
      updateActive((item) => ({
        ...item,
        updatedAt: Date.now(),
        messages: [...item.messages, failureMessage].slice(-24),
      }));
    } finally {
      setSending(false);
    }
  }

  async function handleApproval(approvalId: string, approve: boolean) {
    if (!active) return;
    const endpoint = approve ? "/api/approve" : "/api/cancel";
    setSending(true);
    try {
      const payload = await api<any>(endpoint, {
        method: "POST",
        body: JSON.stringify({ approval_id: approvalId, session_id: active.id }),
      });
      const text = approve ? answerText(payload) : "Action cancelled by user. No change was made.";
      updateActive((item) => ({
        ...item,
        updatedAt: Date.now(),
        messages: item.messages.map((m) =>
          m.approval?.approval_id === approvalId
            ? { role: "assistant", text, status: payload?.status ?? (approve ? "success" : "cancelled") }
            : m
        ),
      }));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Approval request failed.");
    } finally {
      setSending(false);
    }
  }

  function speakText(text: string) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.slice(0, 1000));
    window.speechSynthesis.speak(utterance);
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void sendMessage();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">T</span>
          <span>TARA</span>
        </div>
        <button className="new-chat" onClick={startNewChat}>
          + New chat
        </button>
        <p className="section-label">SAVED CHATS</p>
        <nav className="conversation-list" aria-label="Recent chats">
          {conversations
            .slice()
            .sort((a, b) => b.updatedAt - a.updatedAt)
            .map((item) => (
              <div key={item.id} className="conversation-row">
                <button
                  className={item.id === active?.id ? "conversation active" : "conversation"}
                  onClick={() => setSessionId(item.id)}
                  title={item.title}
                >
                  {item.title}
                </button>
                <button
                  className="conversation-delete"
                  onClick={(e) => void deleteChat(item.id, e)}
                  title="Delete chat"
                  aria-label="Delete chat"
                >
                  ×
                </button>
              </div>
            ))}
        </nav>
        <div className="sidebar-footer">Chats saved locally via SQLite</div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="top-brand">
            <span className="brand-mark large">T</span>
            <div>
              <h1>TARA</h1>
              <p>Intelligent Windows Desktop Assistant</p>
            </div>
          </div>
          <div className="top-actions">
            <span className="local-pill">
              <i /> Local app
            </span>
            <button
              className="secondary"
              onClick={() => {
                setDiagOpen((open) => !open);
                if (modelsOpen) setModelsOpen(false);
              }}
              aria-expanded={diagOpen}
            >
              System Health
            </button>
            <button
              className="secondary"
              onClick={() => {
                setModelsOpen((open) => !open);
                if (diagOpen) setDiagOpen(false);
              }}
              aria-expanded={modelsOpen}
            >
              Models
            </button>
          </div>
        </header>

        {diagOpen && (
          <section className="diagnostics-panel" aria-label="System Diagnostics">
            <div className="panel-heading">
              <div>
                <h2>Windows System Health & Diagnostics</h2>
                <p>Hardware resources, gateway connectivity, and security status.</p>
              </div>
              <button className="secondary" onClick={() => void refreshDiagnostics()} disabled={diagBusy}>
                {diagBusy ? "Checking..." : "Refresh"}
              </button>
            </div>

            {diagnostics && (
              <>
                <div style={{ margin: "10px 0" }}>
                  Status:{" "}
                  <span
                    className={`status-badge badge-${
                      diagnostics.overall_status === "GOOD"
                        ? "good"
                        : diagnostics.overall_status === "NORMAL"
                        ? "normal"
                        : diagnostics.overall_status === "WARNING"
                        ? "warning"
                        : "critical"
                    }`}
                  >
                    {diagnostics.overall_status}
                  </span>
                </div>

                <div className="diag-grid">
                  <div className="diag-card">
                    <div className="diag-card-title">Memory (RAM)</div>
                    <div className="diag-card-value">
                      {diagnostics.hardware.memory.load_percent}% Used
                    </div>
                    <div className="diag-card-sub">
                      {diagnostics.hardware.memory.available_gb} GB Free / {diagnostics.hardware.memory.total_gb} GB Total
                    </div>
                  </div>

                  <div className="diag-card">
                    <div className="diag-card-title">CPU Load</div>
                    <div className="diag-card-value">
                      {diagnostics.hardware.cpu.cpu_percent}%
                    </div>
                    <div className="diag-card-sub">Intel Core i5 (Windows 11)</div>
                  </div>

                  <div className="diag-card">
                    <div className="diag-card-title">SSD Storage</div>
                    <div className="diag-card-value">
                      {diagnostics.hardware.disk.free_gb} GB Free
                    </div>
                    <div className="diag-card-sub">
                      {diagnostics.hardware.disk.percent_used}% of {diagnostics.hardware.disk.total_gb} GB used
                    </div>
                  </div>

                  <div className="diag-card">
                    <div className="diag-card-title">OmniRoute Gateway</div>
                    <div className="diag-card-value" style={{ fontSize: "14px", textTransform: "capitalize" }}>
                      {diagnostics.omniroute.status.replace("_", " ")}
                    </div>
                    <div className="diag-card-sub">{diagnostics.omniroute.base_url}</div>
                  </div>
                </div>

                {diagnostics.issues.length > 0 && (
                  <div style={{ marginTop: "12px" }}>
                    <strong style={{ fontSize: "12px", color: "#f7b443" }}>Recommendations:</strong>
                    <ul style={{ margin: "6px 0 0 16px", padding: 0, fontSize: "12px", color: "#baa47d" }}>
                      {diagnostics.issues.map((issue, idx) => (
                        <li key={idx} style={{ marginBottom: "4px" }}>
                          [{issue.severity}] {issue.component}: {issue.message} — <em>{issue.recommendation}</em>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {modelsOpen && (
          <section className="models-panel">
            <div className="panel-heading">
              <div>
                <h2>OmniRoute models</h2>
                <p>Model selection and routing policies are managed by the OmniRoute gateway.</p>
              </div>
              <button className="secondary" onClick={() => void refreshModels()} disabled={modelBusy === "refresh"}>
                {modelBusy === "refresh" ? "Refreshing..." : "Refresh"}
              </button>
            </div>
            {modelStatus?.status === "managed_externally" && (
              <p className="muted">
                TARA routes model inference to OmniRoute. Use the Model Hub to inspect available models.
              </p>
            )}
            <div className="free-hub">
              <div>
                <strong>OmniRoute Model Hub</strong>
                <p>Browse models exposed by OmniRoute (loopback port 20128).</p>
              </div>
              <button onClick={() => void sendMessage(FREE_MODELS_PROMPT)} disabled={sending}>
                List models
              </button>
            </div>
          </section>
        )}

        {notice && (
          <div className="notice" role="status">
            {notice}
            <button onClick={() => setNotice("")} aria-label="Dismiss notice">
              ×
            </button>
          </div>
        )}

        <section className="chat-area" aria-label="Conversation">
          {!active?.messages.length && (
            <div className="welcome">
              <div className="welcome-mark">✦</div>
              <h2>What can I help with?</h2>
              <p>Your AI desktop assistant with controlled Windows automation and OmniRoute intelligence.</p>
              <div className="prompt-grid">
                {[
                  "Explain a concept simply",
                  "Open Calculator",
                  "Inspect system status",
                  "List all available models",
                ].map((prompt) => (
                  <button key={prompt} onClick={() => void sendMessage(prompt)}>
                    {prompt}
                    <span>→</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="messages">
            {(active?.messages ?? []).map((message, index) => (
              <article key={`${active?.id}-${index}`} className={`message ${message.role}`}>
                <div className="message-label">
                  <span>{message.role === "user" ? "You" : "TARA"}</span>
                  {message.status && message.status !== "success" ? <span>[{message.status}]</span> : null}
                  {message.role === "assistant" && (
                    <button
                      className="icon-speak"
                      onClick={() => speakText(message.text)}
                      title="Read aloud"
                      style={{ background: "transparent", border: "none", color: "#627b82", cursor: "pointer", marginLeft: "6px" }}
                    >
                      🔊
                    </button>
                  )}
                </div>

                <div className={`message-bubble ${message.role === "assistant" ? "markdown-body" : ""}`}>
                  {message.role === "assistant" ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
                  ) : (
                    message.text
                  )}

                  {message.approval && (
                    <div className="approval-card">
                      <h4>🛡️ Security Approval Required</h4>
                      <p>{message.approval.approval_description}</p>
                      <small>One-time approval | Verified through TARA-Security</small>
                      <div className="approval-actions">
                        <button
                          className="approve-button"
                          onClick={() => void handleApproval(message.approval!.approval_id, true)}
                          disabled={sending}
                        >
                          Approve once
                        </button>
                        <button
                          className="cancel-button"
                          onClick={() => void handleApproval(message.approval!.approval_id, false)}
                          disabled={sending}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </article>
            ))}
            {sending && <div className="typing" role="status">TARA is thinking...</div>}
          </div>
        </section>

        {attachments.length > 0 && (
          <div className="attachment-bar">
            {attachments.map((att, idx) => (
              <span key={idx} className="attachment-chip">
                📎 {att.name}
                <button
                  type="button"
                  className="attachment-remove"
                  onClick={() => removeAttachment(idx)}
                  aria-label="Remove attachment"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <form className="composer" onSubmit={submit}>
          <div className="composer-row">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelected}
              style={{ display: "none" }}
              multiple
            />
            <button
              type="button"
              className="attach-button"
              onClick={() => fileInputRef.current?.click()}
              title="Attach files (code, documents, images)"
              aria-label="Attach files"
            >
              📎
            </button>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder="Message TARA (e.g. 'open calculator', 'system status', 'debug code')..."
              aria-label="Message TARA"
              rows={1}
              maxLength={20000}
            />
            <button
              className="send"
              type="submit"
              disabled={sending || (!draft.trim() && !attachments.length)}
              aria-label="Send message"
            >
              {sending ? "..." : "↑"}
            </button>
          </div>
          <p>
            Language-model inference is routed exclusively through OmniRoute. Sensitive system actions require your explicit approval.
          </p>
        </form>
        <footer>TARA Desktop AI Assistant • Windows 11</footer>
      </main>
    </div>
  );
}
