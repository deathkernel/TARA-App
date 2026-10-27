(() => {
  const composer = document.querySelector("#composer");
  const question = document.querySelector("#question");
  const messages = document.querySelector("#messages");
  const welcome = document.querySelector("#welcome");
  const fileInput = document.querySelector("#files");
  const fileList = document.querySelector("#file-list");
  const send = document.querySelector("#send");
  const AUDIO_MEDIA_TYPES = new Set(["audio/mpeg", "audio/wav", "audio/mp4", "audio/webm", "audio/ogg", "audio/flac", "audio/aac"]);
  const AUDIO_SUFFIX_TYPES = { ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".webm": "audio/webm", ".ogg": "audio/ogg", ".flac": "audio/flac", ".aac": "audio/aac" };
  const modelPanel = document.querySelector("#model-panel");
  const modelsToggle = document.querySelector("#models-toggle");
  const modelsRefresh = document.querySelector("#models-refresh");
  const modelServiceStatus = document.querySelector("#model-service-status");
  const modelList = document.querySelector("#model-list");
  let modelPollTimer = null;
  const audioUrls = [];
  let selectedFiles = [];
  const audioTypeFor = file => {
    const declared = file.type.toLowerCase();
    if (AUDIO_MEDIA_TYPES.has(declared)) return declared;
    const suffix = file.name.toLowerCase().match(/\.[^.]+$/)?.[0];
    return AUDIO_SUFFIX_TYPES[suffix] || null;
  };
  const sessionKey = "tara-app-session";
  const conversationStorageKey = "tara-app-conversations";
  const conversationList = document.querySelector("#conversation-list");
  let conversations = [];
  try {
    const stored = JSON.parse(localStorage.getItem(conversationStorageKey) || "[]");
    if (Array.isArray(stored)) {
      conversations = stored.filter(item => item && typeof item.id === "string" && Array.isArray(item.messages))
        .map(item => ({
          id: item.id,
          title: typeof item.title === "string" ? item.title.slice(0, 80) : "New chat",
          updatedAt: Number.isFinite(item.updatedAt) ? item.updatedAt : Date.now(),
          messages: item.messages.filter(message => message && ["user", "answer"].includes(message.role) && typeof message.text === "string")
            .slice(-24).map(message => ({
              role: message.role,
              text: message.text.slice(0, 6000),
              ...(message.hasAttachments === true ? { hasAttachments: true } : {}),
              ...(typeof message.status === "string" ? { status: message.status.slice(0, 40) } : {}),
              ...(typeof message.module === "string" ? { module: message.module.slice(0, 60) } : {}),
              ...(typeof message.action === "string" ? { action: message.action.slice(0, 60) } : {})
            }))
        })).slice(0, 12);
    }
  } catch {
    conversations = [];
  }
  let sessionId = "";
  let editingIndex = null;
  const editBanner = document.querySelector("#edit-banner");
  const editLabel = document.querySelector("#edit-label");
  const cancelEditButton = document.querySelector("#cancel-edit");
  try { sessionId = localStorage.getItem(sessionKey) || ""; } catch {}
  if (!sessionId || !conversations.some(item => item.id === sessionId)) {
    sessionId = crypto.randomUUID();
    conversations.unshift({ id: sessionId, title: "New chat", updatedAt: Date.now(), messages: [] });
    try { localStorage.setItem(sessionKey, sessionId); } catch {}
  }

  function saveConversations() {
    try { localStorage.setItem(conversationStorageKey, JSON.stringify(conversations.slice(0, 12))); } catch {}
  }

  function renderConversationList() {
    if (!conversationList) return;
    conversationList.replaceChildren();
    conversations.forEach(item => {
      const row = document.createElement("div");
      row.className = "conversation-row";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "conversation-item" + (item.id === sessionId ? " active" : "");
      open.textContent = item.title || "New chat";
      open.title = item.title || "New chat";
      open.addEventListener("click", () => selectConversation(item.id));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "conversation-delete";
      remove.textContent = "×";
      remove.title = "Delete chat";
      remove.setAttribute("aria-label", "Delete " + (item.title || "chat"));
      remove.addEventListener("click", () => deleteConversation(item.id));
      row.append(open, remove);
      conversationList.append(row);
    });
  }

  function recordMessage(role, text, metadata = {}) {
    const item = conversations.find(entry => entry.id === sessionId);
    if (!item || !["user", "answer"].includes(role)) return -1;
    const safeText = String(text || "").slice(0, 6000);
    const message = { role, text: safeText };
    if (role === "user" && metadata && metadata.hasAttachments === true) message.hasAttachments = true;
    if (role === "answer" && metadata && typeof metadata === "object") {
      if (typeof metadata.status === "string") message.status = metadata.status.slice(0, 40);
      if (typeof metadata.route?.module === "string") message.module = metadata.route.module.slice(0, 60);
      if (typeof metadata.route?.action === "string") message.action = metadata.route.action.slice(0, 60);
    }
    item.messages.push(message);
    item.messages = item.messages.slice(-24);
    if (role === "user" && item.title === "New chat") {
      item.title = safeText.replace(/\s+/g, " ").trim().slice(0, 48) || "New chat";
    }
    item.updatedAt = Date.now();
    conversations.sort((left, right) => right.updatedAt - left.updatedAt);
    conversations = conversations.slice(0, 12);
    saveConversations();
    renderConversationList();
    return item.messages.length - 1;
  }

  function setConversationNavigationDisabled(disabled) {
    const newChat = document.querySelector("#new-chat");
    if (newChat) newChat.disabled = disabled;
    if (conversationList) conversationList.querySelectorAll("button").forEach(button => { button.disabled = disabled; });
    messages.querySelectorAll(".message-action-button, .code-copy-button").forEach(button => { button.disabled = disabled; });
  }

  function selectConversation(id) {
    if (send.disabled) return;
    const item = conversations.find(entry => entry.id === id);
    if (!item) return;
    sessionId = item.id;
    try { localStorage.setItem(sessionKey, sessionId); } catch {}
    clearEditing();
    question.value = "";
    resizeComposer();
    renderActiveConversation();
    renderConversationList();
    question.focus();
  }

  function newConversation() {
    if (send.disabled) return;
    sessionId = crypto.randomUUID();
    conversations.unshift({ id: sessionId, title: "New chat", updatedAt: Date.now(), messages: [] });
    conversations = conversations.slice(0, 12);
    try { localStorage.setItem(sessionKey, sessionId); } catch {}
    clearEditing();
    question.value = "";
    messages.replaceChildren();
    welcome.hidden = false;
    selectedFiles = [];
    updateFiles();
    saveConversations();
    renderConversationList();
    question.focus();
  }

  function deleteConversation(id) {
    if (send.disabled) return;
    conversations = conversations.filter(item => item.id !== id);
    saveConversations();
    if (sessionId === id) {
      sessionId = "";
      newConversation();
      return;
    }
    renderConversationList();
  }

  function renderActiveConversation() {
    const item = conversations.find(entry => entry.id === sessionId);
    messages.replaceChildren();
    if (!item) {
      welcome.hidden = false;
      return;
    }
    welcome.hidden = item.messages.length > 0;
    item.messages.forEach((message, index) => addMessage(message.role, message.text, false, message, index));
  }

  function restoreActiveConversation() {
    const item = conversations.find(entry => entry.id === sessionId);
    if (!item || !item.messages.length) return;
    renderActiveConversation();
  }

  function addMessage(role, content, persist = true, metadata = {}, indexHint = null) {
    const messageIndex = persist ? recordMessage(role, content, metadata) : indexHint;
    const article = document.createElement("article");
    article.className = "message " + role;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "answer") renderMarkdown(bubble, String(content || ""));
    else bubble.textContent = String(content || "");
    article.append(bubble);
    if (messageIndex !== null && messageIndex >= 0) addMessageActions(article, role, messageIndex, String(content || ""));
    messages.append(article);
    article.scrollIntoView({ behavior: "smooth", block: "end" });
    return article;
  }

  function addMessageActions(article, role, index, text) {
    const item = conversations.find(entry => entry.id === sessionId);
    const message = item && item.messages[index];
    if (!message || message.role !== role) return;
    const actions = document.createElement("div");
    actions.className = "message-actions";
    if (role === "user" && message.hasAttachments !== true) {
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "message-action-button";
      edit.textContent = "Edit";
      edit.setAttribute("aria-label", "Edit this message");
      edit.addEventListener("click", () => startEditing(index));
      actions.append(edit);
    }
    if (role === "answer") {
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "message-action-button";
      copy.textContent = "Copy";
      copy.setAttribute("aria-label", "Copy this answer");
      copy.addEventListener("click", () => copyText(text, copy));
      actions.append(copy);
      const previous = item.messages[index - 1];
      if (index === item.messages.length - 1 && previous && previous.role === "user" && previous.hasAttachments !== true) {
        const regenerate = document.createElement("button");
        regenerate.type = "button";
        regenerate.className = "message-action-button";
        regenerate.textContent = "Regenerate";
        regenerate.setAttribute("aria-label", "Regenerate this answer");
        regenerate.addEventListener("click", () => regenerateAnswer(index));
        actions.append(regenerate);
      }
    }
    if (actions.childElementCount) article.append(actions);
  }

  function historyFor(sourceMessages) {
    const history = [];
    for (let index = 0; index + 1 < sourceMessages.length; index += 1) {
      const user = sourceMessages[index];
      const answer = sourceMessages[index + 1];
      if (!user || user.role !== "user" || user.hasAttachments === true || !answer || answer.role !== "answer") continue;
      if (["failed", "unavailable", "invalid_request", "permission_denied", "cancelled"].includes(answer.status)) continue;
      history.push(
        { role: "user", content: user.text },
        { role: "assistant", content: answer.text }
      );
      index += 1;
    }
    return history.slice(-24);
  }

  function clearEditing() {
    editingIndex = null;
    if (editBanner) editBanner.hidden = true;
    if (editLabel) editLabel.textContent = "";
  }

  function resizeComposer() {
    question.style.height = "auto";
    question.style.height = Math.min(question.scrollHeight, 180) + "px";
  }

  function startEditing(index) {
    if (send.disabled) return;
    const item = conversations.find(entry => entry.id === sessionId);
    const message = item && item.messages[index];
    if (!message || message.role !== "user" || message.hasAttachments === true) return;
    editingIndex = index;
    question.value = message.text;
    if (editLabel) editLabel.textContent = "Editing your message";
    if (editBanner) editBanner.hidden = false;
    resizeComposer();
    question.focus();
  }

  function cancelEditing() {
    clearEditing();
    question.value = "";
    resizeComposer();
    question.focus();
  }

  async function copyText(value, button) {
    const original = button.textContent;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const temporary = document.createElement("textarea");
        temporary.value = value;
        temporary.style.position = "fixed";
        temporary.style.opacity = "0";
        document.body.append(temporary);
        temporary.select();
        const copied = document.execCommand("copy");
        temporary.remove();
        if (!copied) throw new Error("Clipboard is unavailable");
      }
      button.textContent = "Copied";
    } catch {
      button.textContent = "Copy unavailable";
    }
    window.setTimeout(() => { if (button.isConnected) button.textContent = original; }, 1600);
  }

  function regenerateAnswer(index) {
    if (send.disabled) return;
    const item = conversations.find(entry => entry.id === sessionId);
    const answer = item && item.messages[index];
    const user = item && item.messages[index - 1];
    if (!item || index !== item.messages.length - 1 || !answer || answer.role !== "answer" ||
        !user || user.role !== "user" || user.hasAttachments === true) return;
    const prompt = user.text;
    const history = historyFor(item.messages.slice(0, index - 1));
    item.messages = item.messages.slice(0, index);
    item.updatedAt = Date.now();
    saveConversations();
    renderConversationList();
    renderActiveConversation();
    requestPrompt(prompt, [], history, false);
  }

  function appendInlineMarkdown(parent, source) {
    const tick = String.fromCharCode(96);
    const tokenPattern = new RegExp("(\\[[^\\]]+\\]\\(https?:\\/\\/[^\\s)]+\\)|" + tick + "[^" + tick + "]+" + tick + "|\\*\\*[^*]+\\*\\*|__[^_]+__|\\*[^*\\n]+\\*|_[^_\\n]+_)", "g");
    let offset = 0;
    for (const match of source.matchAll(tokenPattern)) {
      if (match.index > offset) parent.append(document.createTextNode(source.slice(offset, match.index)));
      const token = match[0];
      let node;
      if (token.startsWith("[") && token.includes("](")) {
        const split = token.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
        if (split) {
          try {
            const parsed = new URL(split[2]);
            if (["https:", "http:"].includes(parsed.protocol) && !parsed.username && !parsed.password) {
              node = document.createElement("a");
              node.href = parsed.href;
              node.target = "_blank";
              node.rel = "noopener noreferrer";
              node.textContent = split[1];
            }
          } catch {}
        }
      } else if (token.startsWith(tick)) {
        node = document.createElement("code");
        node.className = "inline-code";
        node.textContent = token.slice(1, -1);
      } else if (token.startsWith("**") || token.startsWith("__")) {
        node = document.createElement("strong");
        node.textContent = token.slice(2, -2);
      } else {
        node = document.createElement("em");
        node.textContent = token.slice(1, -1);
      }
      parent.append(node || document.createTextNode(token));
      offset = match.index + token.length;
    }
    if (offset < source.length) parent.append(document.createTextNode(source.slice(offset)));
  }

  function renderMarkdown(container, source) {
    container.classList.add("markdown-content");
    const tick = String.fromCharCode(96);
    const lines = String(source || "").replace(/\r\n?/g, "\n").split("\n");
    let index = 0;
    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) { index += 1; continue; }
      if (line.trimStart().startsWith(tick.repeat(3))) {
        const language = line.trimStart().slice(3).trim().slice(0, 40);
        const codeLines = [];
        index += 1;
        while (index < lines.length && !lines[index].trimStart().startsWith(tick.repeat(3))) codeLines.push(lines[index++]);
        if (index < lines.length) index += 1;
        const wrap = document.createElement("div");
        wrap.className = "code-block-wrap";
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        if (language) code.dataset.language = language;
        code.textContent = codeLines.join("\n");
        pre.append(code);
        const copy = document.createElement("button");
        copy.type = "button";
        copy.className = "code-copy-button";
        copy.textContent = "Copy code";
        copy.addEventListener("click", () => copyText(code.textContent, copy));
        wrap.append(pre, copy);
        container.append(wrap);
        continue;
      }
      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        const node = document.createElement("h" + heading[1].length);
        appendInlineMarkdown(node, heading[2]);
        container.append(node);
        index += 1;
        continue;
      }
      if (/^\s*(?:---+|\*\*\*+|___+)\s*$/.test(line)) {
        container.append(document.createElement("hr"));
        index += 1;
        continue;
      }
      if (/^\s*>/.test(line)) {
        const quote = document.createElement("blockquote");
        const paragraph = document.createElement("p");
        while (index < lines.length && /^\s*>/.test(lines[index])) {
          if (paragraph.childNodes.length) paragraph.append(document.createElement("br"));
          appendInlineMarkdown(paragraph, lines[index++].replace(/^\s*>\s?/, ""));
        }
        quote.append(paragraph);
        container.append(quote);
        continue;
      }
      const listStart = line.match(/^\s*(?:[-+*]\s+|\d+[.)]\s+)/);
      if (listStart) {
        const ordered = /^\s*\d+[.)]/.test(line);
        const list = document.createElement(ordered ? "ol" : "ul");
        while (index < lines.length) {
          const current = lines[index].match(/^\s*(?:([-+*])\s+|(\d+)[.)]\s+)(.+)$/);
          if (!current || Boolean(current[2]) !== ordered) break;
          const item = document.createElement("li");
          appendInlineMarkdown(item, current[3]);
          list.append(item);
          index += 1;
        }
        container.append(list);
        continue;
      }
      const paragraph = document.createElement("p");
      while (index < lines.length && lines[index].trim() &&
        !lines[index].trimStart().startsWith(tick.repeat(3)) &&
        !/^#{1,6}\s+/.test(lines[index]) &&
        !/^\s*>/.test(lines[index]) &&
        !/^\s*(?:[-+*]\s+|\d+[.)]\s+)/.test(lines[index]) &&
        !/^\s*(?:---+|\*\*\*+|___+)\s*$/.test(lines[index])) {
        if (paragraph.childNodes.length) paragraph.append(document.createElement("br"));
        appendInlineMarkdown(paragraph, lines[index++].replace(/\s{2,}$/, ""));
      }
      container.append(paragraph);
    }
  }

  function updateFiles() {
    fileList.replaceChildren();
    fileList.hidden = selectedFiles.length === 0;
    selectedFiles.forEach((file, index) => {
      const chip = document.createElement("span");
      chip.className = "file-chip";
      chip.append(document.createTextNode(file.name));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "x";
      remove.setAttribute("aria-label", `Remove ${file.name}`);
      remove.addEventListener("click", () => {
        selectedFiles.splice(index, 1);
        updateFiles();
      });
      chip.append(remove);
      fileList.append(chip);
    });
  }

  fileInput.addEventListener("change", () => {
    const codeExtensions = new Set([".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".h", ".cc", ".hh", ".hpp", ".cpp", ".cxx", ".cs", ".rb", ".php", ".sh", ".bash", ".zsh", ".ps1", ".sql", ".swift", ".kt", ".kts", ".dart", ".scala", ".lua", ".pl", ".r"]);
    const allowed = file => {
      const name = file.name.toLowerCase();
      return file.type.startsWith("image/") || Boolean(audioTypeFor(file)) ||
        file.type === "text/csv" || name.endsWith(".csv") ||
        codeExtensions.has(name.slice(name.lastIndexOf(".")));
    };
    const additions = Array.from(fileInput.files || []);
    const rejected = additions.filter(file => !allowed(file) || file.size > 512_000);
    if (rejected.length) addMessage("answer", "Attach images, CSV, source-code files, or MP3, WAV, M4A/MP4, WebM, OGG, FLAC, or AAC audio up to 512 KB each.");
    let totalBytes = selectedFiles.reduce((total, file) => total + file.size, 0);
    for (const file of additions.filter(allowed).filter(file => file.size <= 512_000)) {
      if (selectedFiles.length >= 4) break;
      if (totalBytes + file.size > 512_000) {
        addMessage("answer", "The combined attachment limit is 512 KB per message.");
        continue;
      }
      selectedFiles.push(file);
      totalBytes += file.size;
    }
    updateFiles();
    fileInput.value = "";
  });

  async function encodeFile(file) {
    const encoded = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
      reader.readAsDataURL(file);
    });
    return { name: file.name, media_type: audioTypeFor(file) || file.type || (file.name.toLowerCase().endsWith(".csv") ? "text/csv" : "application/octet-stream"), content_base64: encoded };
  }

  function resultText(payload) {
    const data = payload?.result?.data || {};
    if (data.operation === "github.issue.create" && Number.isInteger(data.issue_number)) {
      return "Created GitHub issue #" + data.issue_number + " in " + data.repository + ": " + data.title;
    }
    if (data.stored === true) return 'Saved the note under "' + data.key + '" in TARA-Memory.';
    if (typeof data.forgotten === "boolean") return data.forgotten ? 'Forgot "' + data.key + '" from TARA-Memory.' : 'No saved note matched "' + data.key + '".';
    if (Array.isArray(data.memories)) {
      return data.memories.length ? data.memories.map(item => item.key + ": " + item.value).join("\n") : "No matching saved notes.";
    }
    if (data.cancelled === true) return "Cancelled. No change was made.";
    if (Number.isInteger(data.rows) && Array.isArray(data.columns)) {
      return "Analyzed " + data.rows + " rows across " + data.columns.length + " columns.";
    }
    const steps = Array.isArray(data.steps) ? data.steps : (Array.isArray(data.plan?.steps) ? data.plan.steps : null);
    if (steps) {
      const summary = data.plan?.summary || data.goal || "TARA-Code plan";
      const planText = summary + "\n" + steps.length + " reviewable step" + (steps.length === 1 ? "" : "s") + ".";
      const warnings = Array.isArray(data.plan?.warnings) ? data.plan.warnings.filter(item => typeof item === "string" && item) : [];
      return warnings.length ? planText + "\n\nNotes:\n" + warnings.join("\n") : planText;
    }
    for (const key of ["text", "summary", "description", "transcript"]) {
      if (typeof data[key] === "string" && data[key]) return data[key];
    }
    if (payload?.result?.error) return payload.result.error;
    if (payload?.status === "approval_required") return "TARA-Security reviewed this request. Nothing has run yet.";
    if (payload?.status === "cancelled") return "Cancelled. No change was made.";
    return "The specialist returned a structured result. Open details to inspect it.";
  }

  function appendSpecialistOutput(bubble, payload) {
    const data = payload?.result?.data || {};

    if (data.operation === "github.issue.create" && typeof data.url === "string") {
      try {
        const issueUrl = new URL(data.url);
        if (issueUrl.protocol === "https:" && issueUrl.hostname === "github.com") {
          const link = document.createElement("a");
          link.href = issueUrl.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "Open created GitHub issue";
          bubble.append(link);
        }
      } catch (_) {
        // Ignore malformed provider links.
      }
    }

    if (Array.isArray(data.sources)) {
      const sources = document.createElement("section");
      sources.className = "source-list";
      const heading = document.createElement("strong");
      heading.textContent = "Sources";
      const list = document.createElement("ul");
      for (const source of data.sources.slice(0, 5)) {
        if (!source || typeof source.url !== "string" || typeof source.title !== "string") continue;
        try {
          const sourceUrl = new URL(source.url);
          if (!["https:", "http:"].includes(sourceUrl.protocol) || sourceUrl.username || sourceUrl.password) continue;
          const item = document.createElement("li");
          const link = document.createElement("a");
          link.href = sourceUrl.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = source.title || sourceUrl.hostname;
          item.append(link);
          if (typeof source.snippet === "string" && source.snippet) {
            const snippet = document.createElement("p");
            snippet.textContent = source.snippet;
            item.append(snippet);
          }
          list.append(item);
        } catch (_) {
          continue;
        }
      }
      if (list.childElementCount) {
        sources.append(heading, list);
        bubble.append(sources);
      }
    }

    const numeric = data.numeric_summary;
    if (numeric && typeof numeric === "object" && !Array.isArray(numeric)) {
      const entries = Object.entries(numeric).slice(0, 50);
      if (entries.length) {
        const wrap = document.createElement("div");
        wrap.className = "analysis-table-wrap";
        const table = document.createElement("table");
        table.className = "analysis-table";
        const caption = document.createElement("caption");
        caption.textContent = "Numeric summary";
        table.append(caption);
        const header = document.createElement("tr");
        for (const label of ["Column", "Count", "Min", "Max", "Mean", "Median"]) {
          const cell = document.createElement("th");
          cell.scope = "col";
          cell.textContent = label;
          header.append(cell);
        }
        const head = document.createElement("thead");
        head.append(header);
        const body = document.createElement("tbody");
        for (const [name, values] of entries) {
          if (!values || typeof values !== "object" || Array.isArray(values)) continue;
          const row = document.createElement("tr");
          for (const value of [name, values.count, values.min, values.max, values.mean, values.median]) {
            const cell = document.createElement("td");
            cell.textContent = value === undefined || value === null ? "-" : String(value);
            row.append(cell);
          }
          body.append(row);
        }
        table.append(head, body);
        wrap.append(table);
        bubble.append(wrap);
      }
    }

    const steps = Array.isArray(data.steps) ? data.steps : (Array.isArray(data.plan?.steps) ? data.plan.steps : null);
    if (steps) {
      const list = document.createElement("ol");
      list.className = "plan-steps";
      for (const step of steps.slice(0, 64)) {
        const item = document.createElement("li");
        const title = typeof step.title === "string" ? step.title : "";
        const description = typeof step.description === "string" ? step.description : "";
        item.textContent = title && description ? title + ": " + description : (description || title || "Review this step");
        list.append(item);
      }
      if (list.childElementCount) bubble.append(list);
      const warnings = data.plan?.warnings;
      if (Array.isArray(warnings) && warnings.length) {
        const note = document.createElement("p");
        note.textContent = "Warnings: " + warnings.slice(0, 10).map(String).join("; ");
        bubble.append(note);
      }
    }
  }

  function addResult(payload) {
    const answerText = resultText(payload);
    const messageIndex = recordMessage("answer", answerText, payload);
    const article = document.createElement("article");
    article.className = "message answer";
    const route = payload?.route || {};
    const routeLine = document.createElement("div");
    routeLine.className = "route";
    const specialist = document.createElement("strong");
    specialist.textContent = route.module ? `${route.module}${route.action ? ` | ${route.action}` : ""}` : (route.intended_module || "TARA-App");
    const state = document.createElement("span");
    state.className = `status ${payload?.status || "failed"}`;
    state.textContent = payload?.status || "failed";
    routeLine.append(specialist, state);
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const text = document.createElement("div");
    text.className = "answer-content";
    renderMarkdown(text, answerText);
    bubble.append(text);
    appendSpecialistOutput(bubble, payload);
    const audioData = payload?.result?.data?.audio_base64;
    const mediaType = payload?.result?.data?.media_type;
    if (typeof audioData === "string" && mediaType === "audio/mpeg") {
      const binary = atob(audioData);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      const url = URL.createObjectURL(new Blob([bytes], { type: mediaType }));
      audioUrls.push(url);
      const player = document.createElement("audio");
      player.controls = true;
      player.src = url;
      player.setAttribute("aria-label", "TARA generated speech");
      player.style.display = "block";
      player.style.maxWidth = "100%";
      player.style.marginTop = "12px";
      bubble.append(player);
    }
    const details = document.createElement("details");
    details.className = "details";
    const summary = document.createElement("summary");
    summary.textContent = route.reason ? `Why this route: ${route.reason}` : "Route details";
    const pre = document.createElement("pre");
    const safePayload = JSON.parse(JSON.stringify(payload));
    if (safePayload?.result?.data?.audio_base64) safePayload.result.data.audio_base64 = "[audio bytes omitted]";
    pre.textContent = JSON.stringify(safePayload, null, 2);
    details.append(summary, pre);
    article.append(routeLine, bubble);
    addMessageActions(article, "answer", messageIndex, answerText);
    if (payload?.status === "success" && typeof window.speechSynthesis !== "undefined") {
      const speak = document.createElement("button");
      speak.type = "button";
      speak.className = "read-aloud-button";
      speak.textContent = route.module === "voice" && route.action === "speak" ? "Play with local voice" : "Read aloud locally";
      speak.addEventListener("click", () => {
        const localVoices = window.speechSynthesis.getVoices().filter(voice => voice.localService === true);
        if (!localVoices.length) {
          speak.textContent = "No local speech voice available";
          speak.disabled = true;
          return;
        }
        const utterance = new SpeechSynthesisUtterance(resultText(payload).slice(0, 5000));
        const language = (navigator.language || "").split("-")[0].toLowerCase();
        utterance.voice = localVoices.find(voice => voice.lang.toLowerCase().startsWith(language)) || localVoices[0];
        utterance.lang = utterance.voice.lang;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      });
      article.append(speak);
    }
    const approvalId = payload?.result?.data?.approval_id;
    if (payload?.status === "approval_required" && typeof approvalId === "string") {
      const card = document.createElement("section");
      card.className = "approval-card";
      const description = document.createElement("p");
      description.textContent = payload.result.data.approval_description || `Run ${route.intended_module || "requested specialist"} once?`;
      const expires = document.createElement("small");
      expires.textContent = "One-time approval | expires in 2 minutes";
      const actions = document.createElement("div");
      actions.className = "approval-actions";
      const approve = document.createElement("button");
      approve.type = "button";
      approve.className = "approve-button";
      approve.textContent = "Approve once";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "cancel-button";
      cancel.textContent = "Cancel";
      const act = async endpoint => {
        approve.disabled = true;
        cancel.disabled = true;
        try {
          const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ approval_id: approvalId, session_id: sessionId })
          });
          const outcome = await response.json();
          card.remove();
          addResult(outcome);
        } catch (error) {
          approve.disabled = false;
          cancel.disabled = false;
          addMessage("answer", `Could not update approval: ${error.message || "local server unavailable"}`);
        }
      };
      approve.addEventListener("click", () => act("/api/approve"));
      cancel.addEventListener("click", () => act("/api/cancel"));
      actions.append(approve, cancel);
      card.append(description, expires, actions);
      article.append(card);
    }
    article.append(details);
    messages.append(article);
    article.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  function formatModelBytes(value) {
    if (!Number.isFinite(value) || value < 0) return null;
    const units = ["B", "KiB", "MiB", "GiB", "TiB"];
    let size = value;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) {
      size /= 1024;
      unit += 1;
    }
    return size.toFixed(unit === 0 ? 0 : 1) + " " + units[unit];
  }

  async function refreshModelStatus() {
    if (modelPollTimer !== null) window.clearTimeout(modelPollTimer);
    modelPollTimer = null;
    modelServiceStatus.textContent = "Checking local Ollama...";
    modelsRefresh.disabled = true;
    modelList.replaceChildren();
    try {
      const response = await fetch("/api/models", { headers: { Accept: "application/json" }, cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not read model status");
      if (payload.status === "not_configured") {
        modelServiceStatus.textContent = "No local Ollama profiles are configured.";
        return;
      }
      const pull = payload.pull || {};
      const pullActive = ["queued", "pulling"].includes(pull.status);
      if (pull.status === "failed") {
        modelServiceStatus.textContent = pull.message || "Model download failed. Check Ollama and try again.";
      } else if (pullActive) {
        modelServiceStatus.textContent = "Installing " + String(pull.model || "local model") + "...";
      } else if (payload.service_available !== true) {
        modelServiceStatus.textContent = "Ollama is not responding. Start the local Ollama service, then refresh.";
      } else {
        modelServiceStatus.textContent = "Ollama is available on this device.";
      }
      for (const model of Array.isArray(payload.models) ? payload.models : []) {
        const item = document.createElement("li");
        const profile = document.createElement("div");
        profile.className = "model-profile";
        const specialist = document.createElement("strong");
        specialist.textContent = String(model.specialist || "Specialist");
        const identifier = document.createElement("span");
        identifier.textContent = String(model.model || "Model not configured");
        profile.append(specialist, identifier);
        const state = document.createElement("span");
        state.className = "model-state";
        if (model.running === true) {
          state.textContent = "Loaded";
          state.classList.add("available");
        } else if (model.installed === true) {
          state.textContent = "Installed";
          state.classList.add("available");
        } else if (model.installed === false) {
          state.textContent = "Not installed";
          state.classList.add("missing");
        } else {
          state.textContent = "Unavailable";
          state.classList.add("unavailable");
        }
        const memory = formatModelBytes(model.memory_bytes);
        const vram = formatModelBytes(model.vram_bytes);
        if (memory || vram) {
          const resource = document.createElement("span");
          resource.className = "model-resource";
          resource.textContent = [memory ? "Memory " + memory : "", vram ? "GPU " + vram : ""].filter(Boolean).join(" | ");
          profile.append(resource);
        }
        item.append(profile, state);
        if (model.running === true && !pullActive && !send.disabled) {
          const unload = document.createElement("button");
          unload.type = "button";
          unload.className = "model-unload-button";
          unload.textContent = "Unload";
          unload.setAttribute("aria-label", "Unload " + String(model.model || "configured model") + " from memory");
          unload.addEventListener("click", () => unloadModel(String(model.specialist || "")));
          item.append(unload);
        }
        if (pullActive && pull.specialist === model.specialist) {
          const progressText = document.createElement("span");
          progressText.className = "model-pull-progress";
          const percent = Number.isInteger(pull.percent) ? "Current layer " + pull.percent + "%" : String(pull.message || "Preparing download");
          progressText.textContent = percent;
          const progress = document.createElement("progress");
          progress.max = 100;
          progress.value = Number.isInteger(pull.percent) ? pull.percent : 0;
          progress.setAttribute("aria-label", "Current model layer download progress");
          item.append(progressText, progress);
        } else if (model.installed === false && payload.service_available === true && !pullActive) {
          const install = document.createElement("button");
          install.type = "button";
          install.className = "model-install-button";
          install.textContent = "Install";
          install.setAttribute("aria-label", "Install " + String(model.model || "configured model"));
          install.addEventListener("click", () => startModelPull(String(model.specialist || "")));
          item.append(install);
        } else if (model.installed === true && model.running === false && payload.service_available === true && !pullActive && !send.disabled) {
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "model-remove-button";
          remove.textContent = "Remove";
          remove.setAttribute("aria-label", "Remove " + String(model.model || "configured model") + " from this device");
          const affectedSpecialists = (Array.isArray(payload.models) ? payload.models : [])
            .filter(profile => profile.model === model.model)
            .map(profile => String(profile.specialist || "specialist"));
          remove.addEventListener("click", () => removeModel(
            String(model.specialist || ""),
            String(model.model || "configured model"),
            affectedSpecialists
          ));
          item.append(remove);
        }
        modelList.append(item);
      }
      if (pullActive && !modelPanel.hidden) {
        modelPollTimer = window.setTimeout(refreshModelStatus, 2500);
      }
    } catch (error) {
      modelServiceStatus.textContent = error.message || "Local model status is unavailable.";
    } finally {
      modelsRefresh.disabled = false;
    }
  }

  async function startModelPull(specialist) {
    modelServiceStatus.textContent = "Starting local model download...";
    try {
      const response = await fetch("/api/models/pull", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specialist })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not start model download");
      await refreshModelStatus();
    } catch (error) {
      modelServiceStatus.textContent = error.message || "Could not start local model download.";
    }
  }

  async function unloadModel(specialist) {
    modelServiceStatus.textContent = "Freeing local model memory...";
    try {
      const response = await fetch("/api/models/unload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specialist })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not unload model");
      const message = payload.status === "unloaded"
        ? "Model unloaded from memory. Its installed files remain available."
        : "Model was already unloaded.";
      await refreshModelStatus();
      modelServiceStatus.textContent = message;
    } catch (error) {
      modelServiceStatus.textContent = error.message || "Could not unload local model.";
    }
  }

  async function removeModel(specialist, modelName, affectedSpecialists) {
    const sharedProfiles = affectedSpecialists.length > 1
      ? " This also makes it unavailable for: " + affectedSpecialists.join(", ") + "."
      : "";
    const confirmed = window.confirm(
      "Remove " + modelName + " from this device? It can be installed again later." + sharedProfiles
    );
    if (!confirmed) return;
    modelServiceStatus.textContent = "Removing local model files...";
    try {
      const response = await fetch("/api/models/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specialist })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not remove model");
      const message = payload.status === "removed"
        ? modelName + " removed from this device."
        : modelName + " was already absent.";
      await refreshModelStatus();
      modelServiceStatus.textContent = message;
    } catch (error) {
      modelServiceStatus.textContent = error.message || "Could not remove local model.";
    }
  }

  modelsToggle.addEventListener("click", () => {
    const opening = modelPanel.hidden;
    modelPanel.hidden = !opening;
    modelsToggle.setAttribute("aria-expanded", String(opening));
    if (opening) {
      refreshModelStatus();
    } else if (modelPollTimer !== null) {
      window.clearTimeout(modelPollTimer);
      modelPollTimer = null;
    }
  });
  modelsRefresh.addEventListener("click", refreshModelStatus);

  function addThinkingIndicator() {
    const article = addMessage("answer", "", false);
    const bubble = article.querySelector(".bubble");
    const indicator = document.createElement("div");
    indicator.className = "thinking-indicator";
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-label", "TARA is thinking");
    indicator.setAttribute("aria-live", "polite");
    for (let index = 0; index < 3; index += 1) {
      const dot = document.createElement("span");
      dot.setAttribute("aria-hidden", "true");
      indicator.append(dot);
    }
    bubble.append(indicator);
    return article;
  }

  async function requestPrompt(prompt, files, history, addUser) {
    if (addUser) addMessage("user", prompt, true, { hasAttachments: files.length > 0 });
    welcome.hidden = true;
    question.value = "";
    resizeComposer();
    send.disabled = true;
    setConversationNavigationDisabled(true);
    const pendingFiles = files.splice(0);
    updateFiles();
    const waiting = addThinkingIndicator();
    try {
      const attachments = await Promise.all(pendingFiles.map(encodeFile));
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: prompt, session_id: sessionId, attachments, history })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "TARA could not accept this request");
      waiting.remove();
      addResult(payload);
    } catch (error) {
      waiting.remove();
      addMessage("answer", "TARA could not complete the request: " + (error.message || "local server unavailable"), true, { status: "unavailable" });
    } finally {
      send.disabled = false;
      setConversationNavigationDisabled(false);
      question.focus();
    }
  }

  async function submit() {
    const prompt = question.value.trim();
    if (!prompt || send.disabled) return;
    const item = conversations.find(entry => entry.id === sessionId);
    if (!item) return;
    let history = historyFor(item.messages);
    if (editingIndex !== null) {
      const target = item.messages[editingIndex];
      if (!target || target.role !== "user" || target.hasAttachments === true) {
        clearEditing();
        return;
      }
      history = historyFor(item.messages.slice(0, editingIndex));
      item.messages = item.messages.slice(0, editingIndex);
      item.updatedAt = Date.now();
      saveConversations();
      renderActiveConversation();
      renderConversationList();
      clearEditing();
    }
    const files = selectedFiles.splice(0);
    updateFiles();
    await requestPrompt(prompt, files, history, true);
  }

  renderConversationList();
  restoreActiveConversation();
  document.querySelector("#new-chat")?.addEventListener("click", newConversation);

  composer.addEventListener("submit", event => {
    event.preventDefault();
    submit();
  });
  question.addEventListener("input", resizeComposer);
  cancelEditButton?.addEventListener("click", cancelEditing);
  question.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  });
  document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => {
    question.value = button.dataset.prompt || "";
    question.focus();
    question.dispatchEvent(new Event("input"));
  }));
  window.addEventListener("beforeunload", () => audioUrls.forEach(url => URL.revokeObjectURL(url)));
})();

