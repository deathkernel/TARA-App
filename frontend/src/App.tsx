import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Message = { role: "user" | "assistant"; text: string; status?: string };
type Conversation = { id: string; title: string; updatedAt: number; messages: Message[] };
type LocalModel = {
  specialist: string;
  model: string;
  installed?: boolean | null;
  running?: boolean | null;
  memory_bytes?: number | null;
  vram_bytes?: number | null;
};
type ModelStatus = {
  status: string;
  provider?: string;
  service_available?: boolean;
  models?: LocalModel[];
  pull?: { status?: string; model?: string; message?: string };
};

const STORAGE_KEY = "tara-react-conversations";
const SESSION_KEY = "tara-react-session";
const FREE_MODELS_PROMPT = "List all available free models";

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
    ).slice(0, 12);
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

function formatBytes(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1; }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`;
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
  const [cancelling, setCancelling] = useState(false);
  const activeRequestId = useRef<string | null>(null);
  const activeRequestSession = useRef<string | null>(null);
  const [modelsOpen, setModelsOpen] = useState(false);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [modelBusy, setModelBusy] = useState("");
  const [notice, setNotice] = useState("");

  const active = useMemo(() => conversations.find((item) => item.id === sessionId) ?? conversations[0], [conversations, sessionId]);

  useEffect(() => {
    if (!conversations.length) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...conversations].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 12)));
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
      setNotice(error instanceof Error ? error.message : "Could not read local model status.");
    } finally {
      setModelBusy("");
    }
  }

  useEffect(() => {
    if (modelsOpen && !modelStatus) void refreshModels();
  }, [modelsOpen]);

  function updateActive(transform: (conversation: Conversation) => Conversation) {
    if (!active) return;
    setConversations((items) => items.map((item) => item.id === active.id ? transform(item) : item));
  }

  function startNewChat() {
    const item = newConversation();
    setConversations((items) => [item, ...items].slice(0, 12));
    setSessionId(item.id);
    setDraft("");
    setNotice("");
  }

  async function sendMessage(textOverride?: string) {
    const question = (textOverride ?? draft).trim();
    if (!question || sending || !active) return;
    const history = active.messages.slice(-20).map(({ role, text }) => ({ role, content: text }));
    const userMessage: Message = { role: "user", text: question };
    updateActive((item) => ({
      ...item,
      title: item.title === "New chat" ? question.replace(/\s+/g, " ").slice(0, 48) : item.title,
      updatedAt: Date.now(),
      messages: [...item.messages, userMessage].slice(-24),
    }));
    setDraft("");
    setSending(true);
    setCancelling(false);
    setNotice("");
    const requestId = crypto.randomUUID();
    activeRequestId.current = requestId;
    activeRequestSession.current = active.id;
    try {
      const payload = await api<any>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ question, session_id: active.id, request_id: requestId, attachments: [], history }),
      });
      const text = answerText(payload);
      const assistantMessage: Message = { role: "assistant", text, status: payload?.status ?? "success" };
      updateActive((item) => ({
        ...item, updatedAt: Date.now(),
        messages: [...item.messages, assistantMessage].slice(-24),
      }));
    } catch (error) {
      const failureMessage: Message = {
        role: "assistant",
        text: error instanceof Error ? error.message : "Local server unavailable.",
        status: "unavailable",
      };
      updateActive((item) => ({
        ...item, updatedAt: Date.now(),
        messages: [...item.messages, failureMessage].slice(-24),
      }));
    } finally {
      if (activeRequestId.current === requestId) {
        activeRequestId.current = null;
        activeRequestSession.current = null;
      }
      setSending(false);
      setCancelling(false);
    }
  }

  async function stopMessage() {
    const requestId = activeRequestId.current;
    const requestSession = activeRequestSession.current;
    if (!requestId || !requestSession) return;
    setCancelling(true);
    try {
      const result = await api<{status: string}>("/api/cancel-request", {
        method: "POST",
        body: JSON.stringify({ request_id: requestId, session_id: requestSession }),
      });
      if (result.status !== "cancelled") setNotice("This request could not be stopped at its current stage.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not stop this request.");
    } finally {
      setCancelling(false);
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  async function modelAction(action: "pull" | "unload" | "remove", specialist: string) {
    if (action === "remove" && !window.confirm(`Remove the installed model for ${specialist}? This deletes local model files.`)) return;
    setModelBusy(specialist);
    try {
      await api(`/api/models/${action}`, { method: "POST", body: JSON.stringify({ specialist }) });
      await refreshModels();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Model action failed.");
    } finally {
      setModelBusy("");
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void sendMessage();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">T</span><span>TARA</span></div>
        <button className="new-chat" onClick={startNewChat}>＋ New chat</button>
        <p className="section-label">RECENT CHATS</p>
        <nav className="conversation-list" aria-label="Recent chats">
          {conversations.slice().sort((a, b) => b.updatedAt - a.updatedAt).map((item) => (
            <button key={item.id} className={item.id === active?.id ? "conversation active" : "conversation"} onClick={() => setSessionId(item.id)}>
              {item.title}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">Chats are saved on this device</div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="top-brand"><span className="brand-mark large">T</span><div><h1>TARA</h1><p>Your assistant, routed to the right specialist</p></div></div>
          <div className="top-actions"><span className="local-pill"><i /> Local app</span><button className="secondary" onClick={() => setModelsOpen((open) => !open)} aria-expanded={modelsOpen}>Models</button></div>
        </header>

        {modelsOpen && <section className="models-panel">
          <div className="panel-heading"><div><h2>Local models</h2><p>{modelStatus?.service_available ? "Ollama is available on this device." : "Model inventory and lifecycle controls"}</p></div><button className="secondary" onClick={() => void refreshModels()} disabled={modelBusy === "refresh"}>{modelBusy === "refresh" ? "Refreshing…" : "Refresh"}</button></div>
          {modelStatus?.status === "not_configured" && <p className="muted">No local Ollama profiles are configured.</p>}
          {(modelStatus?.models ?? []).map((model) => <div className="model-card" key={model.specialist}>
            <div><strong>{model.specialist}</strong><p>{model.model}</p><small>{model.memory_bytes ? `RAM ${formatBytes(model.memory_bytes)} · ` : ""}{model.vram_bytes ? `VRAM ${formatBytes(model.vram_bytes)} · ` : ""}{model.running ? "Loaded" : model.installed ? "Installed" : "Not installed"}</small></div>
            <div className="model-actions">
              {!model.installed && <button onClick={() => void modelAction("pull", model.specialist)} disabled={!!modelBusy}>Install</button>}
              {model.installed && model.running && <button className="secondary" onClick={() => void modelAction("unload", model.specialist)} disabled={!!modelBusy}>Unload</button>}
              {model.installed && <button className="danger" onClick={() => void modelAction("remove", model.specialist)} disabled={!!modelBusy}>Remove</button>}
            </div>
          </div>)}
          <div className="free-hub"><div><strong>Free Model Hub</strong><p>Browse free model options without sending a prompt to a cloud provider.</p></div><button onClick={() => void sendMessage(FREE_MODELS_PROMPT)} disabled={sending}>List free models</button></div>
        </section>}

        {notice && <div className="notice" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss notice">×</button></div>}
        <section className="chat-area" aria-label="Conversation">
          {!active?.messages.length && <div className="welcome"><div className="welcome-mark">✦</div><h2>What can I help with?</h2><p>Local-first AI, with each request routed to the right specialist.</p><div className="prompt-grid">
            {["Explain a concept simply", "Make study notes from my file", "Help me debug this code", "List all available free models"].map((prompt) => <button key={prompt} onClick={() => void sendMessage(prompt)}>{prompt}<span>↗</span></button>)}
          </div></div>}
          <div className="messages">
            {(active?.messages ?? []).map((message, index) => <article key={`${active?.id}-${index}`} className={`message ${message.role}`}>
              <div className="message-label">{message.role === "user" ? "You" : "TARA"}{message.status && message.status !== "success" ? <span>{message.status}</span> : null}</div>
              <div className={`message-bubble ${message.role === "assistant" ? "markdown-body" : ""}`}>
                {message.role === "assistant" ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown> : message.text}
              </div>
            </article>)}
            {sending && <div className="typing" role="status">TARA is thinking…</div>}
          </div>
        </section>

        <form className="composer" onSubmit={submit}>
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onComposerKeyDown} placeholder="Message TARA…" aria-label="Message TARA" rows={1} maxLength={20000} />
          {sending ? <button className="secondary" type="button" onClick={() => void stopMessage()} disabled={cancelling}>{cancelling ? "Stopping…" : "Stop"}</button> : <button className="send" type="submit" disabled={!draft.trim()} aria-label="Send message">↑</button>}
          <p>Local inference stays on your device. Cloud requests require explicit configuration.</p>
        </form>
        <footer>Chat and Code are separate specialists · TARA-App</footer>
      </main>
    </div>
  );
}
