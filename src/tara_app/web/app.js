(() => {
  const composer = document.querySelector("#composer");
  const question = document.querySelector("#question");
  const messages = document.querySelector("#messages");
  const welcome = document.querySelector("#welcome");
  const fileInput = document.querySelector("#files");
  const fileList = document.querySelector("#file-list");
  const send = document.querySelector("#send");
  const audioUrls = [];
  let selectedFiles = [];
  const sessionKey = "tara-app-session";
  let sessionId = sessionStorage.getItem(sessionKey);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    sessionStorage.setItem(sessionKey, sessionId);
  }

  function addMessage(role, content) {
    const article = document.createElement("article");
    article.className = `message ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = content;
    article.append(bubble);
    messages.append(article);
    article.scrollIntoView({ behavior: "smooth", block: "end" });
    return article;
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
    const allowed = file => file.type.startsWith("image/") || file.type.startsWith("audio/") || file.type === "text/csv" || file.name.toLowerCase().endsWith(".csv");
    const additions = Array.from(fileInput.files || []);
    const rejected = additions.filter(file => !allowed(file) || file.size > 512_000);
    if (rejected.length) addMessage("answer", "Attach images, audio, or CSV files up to 512 KB each.");
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
    return { name: file.name, media_type: file.type || (file.name.toLowerCase().endsWith(".csv") ? "text/csv" : "application/octet-stream"), content_base64: encoded };
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
      return summary + "\n" + steps.length + " reviewable step" + (steps.length === 1 ? "" : "s") + ".";
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
    text.textContent = resultText(payload);
    bubble.append(text);\n    appendSpecialistOutput(bubble, payload);
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

  async function submit() {
    const prompt = question.value.trim();
    if (!prompt || send.disabled) return;
    welcome.hidden = true;
    addMessage("user", prompt);
    question.value = "";
    question.style.height = "auto";
    send.disabled = true;
    const files = selectedFiles.splice(0);
    updateFiles();
    const waiting = addMessage("answer", "TARA is selecting a specialist...");
    try {
      const attachments = await Promise.all(files.map(encodeFile));
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: prompt, session_id: sessionId, attachments })
      });
      const payload = await response.json();
      waiting.remove();
      addResult(payload);
    } catch (error) {
      waiting.remove();
      addMessage("answer", `TARA could not complete the request: ${error.message || "local server unavailable"}`);
    } finally {
      send.disabled = false;
      question.focus();
    }
  }

  composer.addEventListener("submit", event => {
    event.preventDefault();
    submit();
  });
  question.addEventListener("input", () => {
    question.style.height = "auto";
    question.style.height = `${Math.min(question.scrollHeight, 180)}px`;
  });
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

