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
      remove.textContent = "Ã—";
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
    for (const key of ["text", "summary", "description", "transcript"]) {
      if (typeof data[key] === "string" && data[key]) return data[key];
    }
    if (payload?.result?.error) return payload.result.error;
    if (payload?.status === "approval_required") return "This request needs human approval. No change was made.";
    return "The specialist returned a structured result. Open details to inspect it.";
  }

  function addResult(payload) {
    const article = document.createElement("article");
    article.className = "message answer";
    const route = payload?.route || {};
    const routeLine = document.createElement("div");
    routeLine.className = "route";
    const specialist = document.createElement("strong");
    specialist.textContent = route.module ? `${route.module}${route.action ? ` Â· ${route.action}` : ""}` : (route.intended_module || "TARA-App");
    const state = document.createElement("span");
    state.className = `status ${payload?.status || "failed"}`;
    state.textContent = payload?.status || "failed";
    routeLine.append(specialist, state);
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const text = document.createElement("div");
    text.className = "answer-content";
    text.textContent = resultText(payload);
    bubble.append(text);
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
    article.append(routeLine, bubble, details);
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
    const waiting = addMessage("answer", "TARA is selecting a specialistâ€¦");
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

