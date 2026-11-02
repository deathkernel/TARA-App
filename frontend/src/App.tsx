import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Message = { role: "user" | "assistant"; text: string; status?: string };
type Conversation = { id: string; title: string; updatedAt: number; messages: Message[] };
type LocalModel = { specialist: string; model: string; installed?: boolean | null; running?: boolean | null; memory_bytes?: number | null; vram_bytes?: number | null };
type ModelStatus = { status: string; provider?: string; service_available?: boolean; models?: LocalModel[]; pull?: { status?: string; model?: string; message?: string } };
type HealthStatus = { status?: string; capability_count?: number; capabilities?: string[]; model_runtime?: string };

const STORAGE_KEY = "tara-react-conversations";
const SESSION_KEY = "tara-react-session";
const FREE_MODELS_PROMPT = "List all available free models";

function newConversation(): Conversation { return { id: crypto.randomUUID(), title: "New chat", updatedAt: Date.now(), messages: [] }; }
function readConversations(): Conversation[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is Conversation => !!item && typeof item.id === "string" && typeof item.title === "string" && Array.isArray(item.messages) && item.messages.every((m: unknown) => !!m && typeof m === "object" && "text" in m && typeof m.text === "string" && "role" in m && (m.role === "user" || m.role === "assistant"))).slice(0, 40);
  } catch { return []; }
}
function errorText(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string") return payload.error;
  return fallback;
}
function answerText(payload: any): string {
  const candidates = [payload?.result?.data?.text, payload?.result?.data?.reply, payload?.result?.data?.answer, payload?.result?.error, payload?.result?.data?.message, payload?.error];
  return candidates.find((value) => typeof value === "string" && value.trim()) ?? JSON.stringify(payload, null, 2);
}
function formatBytes(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"]; let size = value; let index = 0;
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1; }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`;
}
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers }, cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorText(payload, `Request failed (${response.status})`));
  return payload as T;
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>(() => { const saved = readConversations(); return saved.length ? saved : [newConversation()]; });
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) ?? "");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [modelsOpen, setModelsOpen] = useState(false);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [modelBusy, setModelBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [copied, setCopied] = useState(-1);

  const active = useMemo(() => conversations.find((item) => item.id === sessionId) ?? conversations[0], [conversations, sessionId]);
  const filtered = useMemo(() => conversations.slice().sort((a,b) => b.updatedAt-a.updatedAt).filter((item) => item.title.toLowerCase().includes(search.toLowerCase())), [conversations, search]);

  useEffect(() => { localStorage.setItem(STORAGE_KEY, JSON.stringify([...conversations].sort((a,b) => b.updatedAt-a.updatedAt).slice(0,40))); }, [conversations]);
  useEffect(() => { if (!active) return; if (active.id !== sessionId) setSessionId(active.id); localStorage.setItem(SESSION_KEY, active.id); }, [active, sessionId]);
  useEffect(() => { void api<HealthStatus>("/api/health").then(setHealth).catch(() => setHealth({status:"offline"})); }, []);

  async function refreshModels() {
    setModelBusy("refresh");
    try { setModelStatus(await api<ModelStatus>("/api/models")); setNotice(""); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Could not read model status."); }
    finally { setModelBusy(""); }
  }
  useEffect(() => { if (modelsOpen && !modelStatus) void refreshModels(); }, [modelsOpen]);

  function updateActive(transform: (conversation: Conversation) => Conversation) {
    if (!active) return;
    setConversations((items) => items.map((item) => item.id === active.id ? transform(item) : item));
  }
  function startNewChat() {
    const item = newConversation(); setConversations((items) => [item, ...items].slice(0,40));
    setSessionId(item.id); setDraft(""); setNotice(""); setSidebarOpen(false);
  }
  function deleteConversation(id: string) {
    const remaining = conversations.filter((item) => item.id !== id);
    const next = remaining.length ? remaining : [newConversation()];
    setConversations(next);
    if (active?.id === id) setSessionId(next[0].id);
  }
  async function sendMessage(textOverride?: string) {
    const question = (textOverride ?? draft).trim();
    if (!question || sending || !active) return;
    const history = active.messages.slice(-20).map(({role,text}) => ({role,content:text}));
    const userMessage: Message = {role:"user",text:question};
    updateActive((item) => ({...item,title:item.title === "New chat" ? question.replace(/\\s+/g," ").slice(0,48) : item.title,updatedAt:Date.now(),messages:[...item.messages,userMessage].slice(-24)}));
    setDraft(""); setSending(true); setNotice("");
    try {
      const payload = await api<any>("/api/chat",{method:"POST",body:JSON.stringify({question,session_id:active.id,attachments:[],history})});
      const assistantMessage: Message = {role:"assistant",text:answerText(payload),status:payload?.status ?? "success"};
      updateActive((item) => ({...item,updatedAt:Date.now(),messages:[...item.messages,assistantMessage].slice(-24)}));
    } catch(error) {
      updateActive((item) => ({...item,updatedAt:Date.now(),messages:[...item.messages,{role:"assistant",text:error instanceof Error ? error.message : "Local server unavailable.",status:"unavailable"}].slice(-24)}));
    } finally { setSending(false); }
  }
  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendMessage(); }
  }
  async function modelAction(action:"pull"|"unload"|"remove", specialist:string) {
    if (action === "remove" && !window.confirm(`Remove the installed model for ${specialist}? This deletes local model files.`)) return;
    setModelBusy(specialist);
    try { await api(`/api/models/${action}`,{method:"POST",body:JSON.stringify({specialist})}); setModelStatus(null); await refreshModels(); }
    catch(error) { setNotice(error instanceof Error ? error.message : "Model action failed."); }
    finally { setModelBusy(""); }
  }
  function submit(event:FormEvent) { event.preventDefault(); void sendMessage(); }
  async function copyMessage(text:string,index:number) {
    try { await navigator.clipboard.writeText(text); setCopied(index); window.setTimeout(() => setCopied(-1),1500); }
    catch { setNotice("Clipboard access is unavailable in this browser."); }
  }
  function renameConversation(id:string) {
    const current = conversations.find((item) => item.id === id);
    const title = window.prompt("Rename conversation",current?.title ?? "");
    if (title?.trim()) setConversations((items) => items.map((item) => item.id === id ? {...item,title:title.trim().slice(0,64)} : item));
  }

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="mobile-scrim" aria-label="Close sidebar" onClick={() => setSidebarOpen(false)} />}
      <aside className={sidebarOpen ? "sidebar sidebar-open" : "sidebar"}>
        <div className="sidebar-head">
          <a className="brand" href="#" onClick={(e)=>e.preventDefault()}><span className="brand-mark">T</span><span className="brand-name">tara<span className="brand-dot">.</span></span></a>
          <button className="icon-button sidebar-close" onClick={()=>setSidebarOpen(false)} aria-label="Close sidebar">×</button>
        </div>
        <button className="new-chat" onClick={startNewChat}><span className="plus-icon">＋</span> New chat <kbd>⌘ K</kbd></button>
        <div className="sidebar-search"><span>⌕</span><input value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Search conversations" aria-label="Search conversations"/><kbd>⌘ F</kbd></div>
        <div className="side-section-title">WORKSPACE</div>
        <button className="side-link selected" onClick={()=>{setModelsOpen(false);setSidebarOpen(false);}}><span className="side-icon">◫</span> Chat</button>
        <button className="side-link" onClick={()=>{setModelsOpen(true);setSidebarOpen(false);}}><span className="side-icon">◈</span> Models & providers</button>
        <div className="history-heading"><span>RECENT</span><span>{filtered.length}</span></div>
        <nav className="conversation-list" aria-label="Recent conversations">
          {filtered.map((item)=>(
            <div className={item.id===active?.id?"conversation-row active":"conversation-row"} key={item.id}>
              <button className="conversation" onClick={()=>{setSessionId(item.id);setSidebarOpen(false);}} title={item.title}><span className="conversation-bullet">·</span>{item.title}</button>
              <div className="conversation-menu">
                <button className="icon-button tiny" aria-label="Rename conversation" title="Rename" onClick={()=>renameConversation(item.id)}>···</button>
                <button className="icon-button tiny delete-chat" aria-label="Delete conversation" title="Delete" onClick={()=>deleteConversation(item.id)}>×</button>
              </div>
            </div>
          ))}
          {!filtered.length && <p className="empty-search">No matching conversations</p>}
        </nav>
        <div className="sidebar-bottom">
          <div className="account-card"><div className="avatar">T</div><div className="account-copy"><strong>TARA Workspace</strong><span>Personal environment</span></div><span className="account-more">···</span></div>
          <div className="privacy-note"><span className="privacy-dot"/> Local app · Your workspace</div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left"><button className="icon-button mobile-menu" onClick={()=>setSidebarOpen(true)} aria-label="Open sidebar">☰</button><div className="context-title"><span className="context-name">Chat</span><span className="context-divider">/</span><span className="context-subtitle">New conversation</span></div></div>
          <div className="top-actions"><div className={health?.status==="offline"?"connection-pill offline":"connection-pill"}><i/>{health?.status==="offline"?"Disconnected":"TARA ready"}</div><button className={modelsOpen?"top-action active":"top-action"} onClick={()=>setModelsOpen((v)=>!v)} aria-expanded={modelsOpen}><span>◈</span> Models</button><button className="icon-button top-more" title="New chat" onClick={startNewChat}>＋</button></div>
        </header>

        {modelsOpen && <section className="models-panel">
          <div className="panel-heading"><div><span className="eyebrow">RUNTIME CONTROL</span><h2>Models & providers</h2><p>{modelStatus?.service_available?"Ollama is available on this device.":"Manage local model inventory and lifecycle."}</p></div><button className="soft-button" onClick={()=>void refreshModels()} disabled={modelBusy==="refresh"}>{modelBusy==="refresh"?"Refreshing…":"↻ Refresh"}</button></div>
          {modelStatus?.status==="not_configured" && <p className="muted">No local Ollama profiles are configured.</p>}
          {(modelStatus?.models??[]).map((model)=><div className="model-card" key={model.specialist}><div className="model-info"><strong>{model.specialist}</strong><p>{model.model}</p><small>{model.memory_bytes?`RAM ${formatBytes(model.memory_bytes)} · `:""}{model.vram_bytes?`VRAM ${formatBytes(model.vram_bytes)} · `:""}{model.running?"Loaded":model.installed?"Installed":"Not installed"}</small></div><div className="model-actions">{!model.installed&&<button onClick={()=>void modelAction("pull",model.specialist)} disabled={!!modelBusy}>Install</button>}{model.installed&&model.running&&<button className="soft-button" onClick={()=>void modelAction("unload",model.specialist)} disabled={!!modelBusy}>Unload</button>}{model.installed&&<button className="danger-button" onClick={()=>void modelAction("remove",model.specialist)} disabled={!!modelBusy}>Remove</button>}</div></div>)}
          <div className="free-hub"><div><strong>Free Model Hub</strong><p>Ask TARA to list free model options.</p></div><button onClick={()=>{setModelsOpen(false);void sendMessage(FREE_MODELS_PROMPT);}} disabled={sending}>Explore models ↗</button></div>
        </section>}

        {notice&&<div className="notice" role="status">{notice}<button onClick={()=>setNotice("")} aria-label="Dismiss notice">×</button></div>}
        <section className="chat-area" aria-label="Conversation">
          {!active?.messages.length ? <div className="welcome">
            <div className="welcome-orbit"><span>✳</span><i/><b/></div>
            <div className="welcome-kicker">YOUR AI WORKSPACE</div>
            <h1>What are we <em>working on</em> today?</h1>
            <p>Think, build, explore. TARA brings your tools and AI specialists together.</p>
            <div className="prompt-grid">
              <button onClick={()=>void sendMessage("Help me understand a complex topic step by step.")}><span className="prompt-icon violet">✧</span><span><strong>Learn something</strong><small>Break down any complex topic</small></span><b>↗</b></button>
              <button onClick={()=>void sendMessage("Help me debug and improve my code.")}><span className="prompt-icon blue">⌘</span><span><strong>Build with code</strong><small>Debug, review and plan changes</small></span><b>↗</b></button>
              <button onClick={()=>void sendMessage("Research this topic and provide sources.")}><span className="prompt-icon amber">⌕</span><span><strong>Research a topic</strong><small>Explore sources and evidence</small></span><b>↗</b></button>
              <button onClick={()=>void sendMessage("Create a practical plan for my project.")}><span className="prompt-icon green">☷</span><span><strong>Plan a project</strong><small>Turn ideas into clear next steps</small></span><b>↗</b></button>
            </div>
          </div> : <div className="messages">
            {active.messages.map((message,index)=><article key={`${active.id}-${index}`} className={`message ${message.role}`}>
              <div className="message-avatar">{message.role==="user"?"S":"✳"}</div>
              <div className="message-content"><div className="message-meta"><strong>{message.role==="user"?"You":"TARA"}</strong>{message.role==="assistant"&&<span className="assistant-tag">Assistant</span>}{message.status&&message.status!=="success"&&<span className="message-status">{message.status}</span>}</div>
                <div className={message.role==="assistant"?"message-text markdown-body":"message-text user-text"}>{message.role==="assistant"?<ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>:message.text}</div>
                {message.role==="assistant"&&<div className="message-tools"><button onClick={()=>void copyMessage(message.text,index)}>{copied===index?"✓ Copied":"▢ Copy"}</button><button onClick={()=>void sendMessage(active.messages.slice(0,index).reverse().find((m)=>m.role==="user")?.text??"")}>↻ Regenerate</button></div>}
              </div>
            </article>)}
            {sending&&<div className="thinking-row"><div className="message-avatar assistant-avatar">✳</div><div><div className="thinking-label">TARA is thinking</div><div className="thinking-dots"><i/><i/><i/></div></div></div>}
          </div>}
        </section>

        <div className="composer-wrap">
          <form className="composer" onSubmit={submit}>
            <textarea value={draft} onChange={(event)=>setDraft(event.target.value)} onKeyDown={onComposerKeyDown} placeholder="Message TARA…" aria-label="Message TARA" rows={1} maxLength={20000}/>
            <div className="composer-bottom"><div className="composer-hints"><span className="composer-spark">✳</span><span>Ask anything</span><span className="hint-divider">·</span><span>Shift + Enter for new line</span></div><button className="send" type="submit" disabled={sending||!draft.trim()} aria-label="Send message">{sending?"…":"↑"}</button></div>
          </form>
          <p className="composer-disclaimer">TARA can make mistakes. Verify important information.</p>
        </div>
        <footer><span>✳</span> TARA · Your AI workspace</footer>
      </main>
    </div>
  );
}
