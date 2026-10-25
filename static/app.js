const $ = (id) => document.getElementById(id);

const state = {
  docs: [],
  current: null,     // current doc meta
  chats: {},         // doc_id -> [{role, content, sources}]
  busy: false,
  sourceLoadedFor: null,
};

// ---------- utils ----------

// \[..\], $$..$$ (display) and \(..\), $..$ (inline)
const MATH_RE = /\\\[([\s\S]+?)\\\]|\$\$([\s\S]+?)\$\$|\\\(([\s\S]+?)\\\)|\$(?!\s)((?:\\.|[^$\\\n])+?)(?<!\s)\$(?!\d)/g;

function renderMath(tex, display) {
  try {
    return katex.renderToString(tex.trim(), { displayMode: display, throwOnError: false, output: "html" });
  } catch {
    return escapeHtml(tex);
  }
}

function md(text) {
  if (window.marked && window.DOMPurify) {
    text = text || "";
    // Pull math out before marked sees it, otherwise "\(" becomes "(" and "_"/"|" get mangled.
    const math = [];
    if (window.katex) {
      text = text.replace(MATH_RE, (_, d1, d2, i1, i2) => {
        const display = d1 !== undefined || d2 !== undefined;
        math.push(renderMath(d1 ?? d2 ?? i1 ?? i2, display));
        return `MATHPH${math.length - 1}X`;
      });
    }
    const html = DOMPurify.sanitize(marked.parse(text))
      // wrapper scrolls wide tables while the table itself stays full width
      .replace(/<table>/g, '<div class="table-wrap"><table>')
      .replace(/<\/table>/g, "</table></div>");
    return html.replace(/MATHPH(\d+)X/g, (_, i) => math[i]);
  }
  const pre = document.createElement("pre");
  pre.textContent = text || "";
  return pre.outerHTML;
}

function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast" + (isError ? " error" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), isError ? 6000 : 2500);
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

// POST and read a text/event-stream response, calling onEvent for each JSON event
async function streamEvents(path, body, onEvent) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (line.startsWith("data:")) onEvent(JSON.parse(line.slice(5)));
    }
  }
}

// ---------- theme ----------

function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("theme"); } catch {}
  if (saved) document.documentElement.dataset.theme = saved;
  $("themeToggle").onclick = () => {
    const cur = document.documentElement.dataset.theme
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
  };
}

// ---------- status ----------

async function loadStatus() {
  try {
    const s = await api("/api/status");
    const box = $("statusBox");
    box.innerHTML = "";
    if (!s.groq_configured) {
      box.innerHTML += `<div class="warn"><b>Groq API key missing.</b> Copy <code>.env.example</code> to <code>.env</code>, add your key, and restart.</div>`;
    }
    if (!s.ocr_available) {
      box.innerHTML += `<div class="warn">Tesseract OCR not found. Scanned PDFs and images can't be read until it's installed (see README).</div>`;
    }
    $("fileInput").accept = s.supported.join(",");
  } catch {}
}

// ---------- documents ----------

async function loadDocs(selectId) {
  state.docs = await api("/api/docs");
  renderDocList();
  if (selectId) openDoc(selectId);
}

function renderDocList() {
  const ul = $("docList");
  ul.innerHTML = "";
  if (!state.docs.length) {
    ul.innerHTML = `<li class="empty-msg">No documents yet</li>`;
    return;
  }
  for (const d of state.docs) {
    const li = document.createElement("li");
    li.className = state.current?.id === d.id ? "active" : "";
    li.title = d.files.join("\n");
    li.innerHTML = `<span class="name"></span><span class="badge">${d.has_notes ? "✓ notes" : ""}</span>
      <button class="del" title="Delete">✕</button>`;
    li.querySelector(".name").textContent = d.title;
    li.onclick = () => openDoc(d.id);
    li.querySelector(".del").onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete "${d.title}"?`)) return;
      await api(`/api/docs/${d.id}`, { method: "DELETE" });
      delete state.chats[d.id];
      if (state.current?.id === d.id) closeDoc();
      loadDocs();
    };
    ul.appendChild(li);
  }
}

function closeDoc() {
  state.current = null;
  $("docView").classList.add("hidden");
  $("emptyState").classList.remove("hidden");
}

async function openDoc(id) {
  if (state.busy) return toast("Please wait for the current task to finish");
  const doc = await api(`/api/docs/${id}`);
  state.current = doc;
  state.sourceLoadedFor = null;
  $("sidebar").classList.remove("open");
  $("emptyState").classList.add("hidden");
  $("docView").classList.remove("hidden");
  $("docTitle").textContent = doc.title;

  const parts = [
    `${doc.files.length} file${doc.files.length > 1 ? "s" : ""}`,
    `${doc.segments} sections`,
    `~${Math.round(doc.chars / 5).toLocaleString()} words`,
  ];
  if (doc.ocr_segments) parts.push(`${doc.ocr_segments} OCR'd`);
  $("docMeta").innerHTML = parts.join(" · ")
    + (doc.warnings?.length ? `<div class="w">⚠ ${doc.warnings.map(escapeHtml).join("<br>⚠ ")}</div>` : "");
  $("downloadBtn").href = `/api/docs/${id}/notes.md`;
  renderDocList();
  renderChat();
  switchTab("notes");

  if (doc.notes) showNotes(doc.notes);
  else generateNotes(false);
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ---------- upload ----------

async function uploadFiles(files) {
  if (!files.length) return;
  const dz = $("dropzone");
  const form = new FormData();
  for (const f of files) form.append("files", f);
  dz.classList.add("busy");
  dz.querySelector(".dz-title").textContent = `Reading ${files.length} file${files.length > 1 ? "s" : ""}…`;
  try {
    const meta = await api("/api/upload", { method: "POST", body: form });
    if (meta.warnings?.length) toast(meta.warnings.join(" · "), true);
    await loadDocs(meta.id);
  } catch (e) {
    toast(e.message, true);
  } finally {
    dz.classList.remove("busy");
    dz.querySelector(".dz-title").textContent = "Drop files or click to upload";
    $("fileInput").value = "";
  }
}

function initUpload() {
  const dz = $("dropzone");
  $("fileInput").onchange = (e) => uploadFiles([...e.target.files]);
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault(); dz.classList.add("drag");
  }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault(); dz.classList.remove("drag");
  }));
  dz.addEventListener("drop", (e) => uploadFiles([...e.dataTransfer.files]));
}

// ---------- notes ----------

function showNotes(markdown) {
  const el = $("notes");
  el.innerHTML = md(markdown);
  // make revision checklist interactive
  el.querySelectorAll('input[type="checkbox"]').forEach((cb) => cb.removeAttribute("disabled"));
  styleCallouts(el);
  wrapBeyond(el);
  el.dataset.raw = markdown;
}

// "> **Example:** ..." blockquotes become coloured callouts
function styleCallouts(el) {
  const kinds = { example: "example", intuition: "intuition", "watch out": "warn", tip: "intuition", note: "intuition" };
  el.querySelectorAll("blockquote").forEach((bq) => {
    const label = bq.querySelector("strong")?.textContent.replace(/:$/, "").trim().toLowerCase();
    if (kinds[label]) bq.classList.add("callout", `callout-${kinds[label]}`);
  });
}

// Group the "Beyond the Notes" section so it's visibly separate from the uploaded material
function wrapBeyond(el) {
  const h2 = [...el.querySelectorAll("h2")].find((h) => h.textContent.trim() === "Beyond the Notes");
  if (!h2) return;
  const box = document.createElement("section");
  box.className = "beyond";
  h2.before(box);
  let next = h2;
  while (next && !(next !== h2 && next.tagName === "H2")) {
    const after = next.nextElementSibling;
    box.appendChild(next);
    next = after;
  }
  const note = document.createElement("p");
  note.className = "beyond-note";
  note.textContent = "Not from your uploaded files: related material from the AI's general knowledge. "
    + "Check anything important against your course before relying on it in an exam.";
  h2.after(note);
}

async function generateNotes(regenerate) {
  const doc = state.current;
  if (!doc || state.busy) return;
  state.busy = true;
  setNotesButtons(false);
  $("notes").innerHTML = "";
  const prog = $("progress");
  prog.classList.remove("hidden");
  $("progressText").textContent = "Starting…";
  $("progressFill").style.width = "3%";
  try {
    await streamEvents(`/api/docs/${doc.id}/notes?regenerate=${regenerate}`, null, (ev) => {
      if (state.current?.id !== doc.id) return;
      if (ev.type === "progress") {
        $("progressText").textContent = ev.message;
        $("progressFill").style.width = `${Math.max(3, (ev.done / ev.total) * 100)}%`;
      } else if (ev.type === "notes") {
        showNotes(ev.markdown);
        doc.notes = ev.markdown;
      } else if (ev.type === "error") {
        $("notes").innerHTML = `<p class="msg error">${escapeHtml(ev.message)}</p>`;
      }
    });
  } catch (e) {
    $("notes").innerHTML = `<p class="msg error">${escapeHtml(e.message)}</p>`;
  } finally {
    prog.classList.add("hidden");
    state.busy = false;
    setNotesButtons(true);
    const d = state.docs.find((x) => x.id === doc.id);
    if (d && doc.notes) { d.has_notes = true; renderDocList(); }
  }
}

function setNotesButtons(enabled) {
  ["regenBtn", "copyBtn", "printBtn"].forEach((id) => ($(id).disabled = !enabled));
}

function initNotes() {
  $("regenBtn").onclick = () => {
    if (confirm("Regenerate notes? This calls the AI again.")) generateNotes(true);
  };
  $("copyBtn").onclick = async () => {
    try {
      await navigator.clipboard.writeText($("notes").dataset.raw || "");
      toast("Notes copied as Markdown");
    } catch { toast("Couldn't access clipboard", true); }
  };
  $("printBtn").onclick = () => window.print();
}

// ---------- chat ----------

function chatFor(id) {
  return (state.chats[id] ||= []);
}

function renderChat() {
  const log = $("chatLog");
  log.innerHTML = "";
  const msgs = chatFor(state.current.id);
  for (const m of msgs) log.appendChild(renderMsg(m));
  $("suggestions").classList.toggle("hidden", msgs.length > 0);
}

function renderMsg(m) {
  const div = document.createElement("div");
  div.className = `msg ${m.role}` + (m.error ? " error" : "");
  if (m.role === "user") div.textContent = m.content;
  else {
    div.innerHTML = md(m.content);
    if (m.sources?.length) {
      const s = document.createElement("div");
      s.className = "sources";
      s.textContent = "Searched: " + m.sources.join(", ");
      div.appendChild(s);
    }
  }
  return div;
}

async function sendChat(text) {
  const doc = state.current;
  text = text.trim();
  if (!doc || !text || state.busy) return;
  state.busy = true;
  $("sendBtn").disabled = true;
  const msgs = chatFor(doc.id);
  msgs.push({ role: "user", content: text });
  const reply = { role: "assistant", content: "", sources: [] };
  msgs.push(reply);
  renderChat();
  const el = $("chatLog").lastElementChild;
  el.classList.add("typing");
  el.scrollIntoView({ block: "end" });

  const payload = msgs.slice(0, -1).filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
  // Re-rendering markdown on every token is O(n^2); render at most once per frame instead
  let frame = 0;
  const render = () => {
    frame = 0;
    if (state.current?.id !== doc.id) return;
    el.innerHTML = md(reply.content);
    const main = document.querySelector(".main");
    main.scrollTop = main.scrollHeight;
  };
  try {
    await streamEvents(`/api/docs/${doc.id}/chat`, { messages: payload }, (ev) => {
      if (ev.type === "sources") reply.sources = ev.sources;
      else if (ev.type === "delta") {
        reply.content += ev.text;
        frame ||= requestAnimationFrame(render);
      } else if (ev.type === "error") {
        reply.content = ev.message;
        reply.error = true;
      }
    });
  } catch (e) {
    reply.content = e.message;
    reply.error = true;
  } finally {
    cancelAnimationFrame(frame);
    state.busy = false;
    $("sendBtn").disabled = false;
    if (state.current?.id === doc.id) renderChat();
    $("chatLog").lastElementChild?.scrollIntoView({ block: "end" });
  }
}

function initChat() {
  const ta = $("chatText");
  $("chatForm").onsubmit = (e) => {
    e.preventDefault();
    const t = ta.value;
    ta.value = "";
    ta.style.height = "";
    sendChat(t);
  };
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("chatForm").requestSubmit(); }
  });
  ta.addEventListener("input", () => {
    ta.style.height = "auto";
    ta.style.height = ta.scrollHeight + "px";
  });
  document.querySelectorAll("#suggestions .chip").forEach((c) => (c.onclick = () => sendChat(c.textContent)));
}

// ---------- tabs ----------

async function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  ["notes", "chat", "source"].forEach((n) => $(`tab-${n}`).classList.toggle("hidden", n !== name));
  if (name === "chat") $("chatText").focus();
  if (name === "source" && state.current && state.sourceLoadedFor !== state.current.id) {
    $("sourceText").textContent = "Loading…";
    const res = await fetch(`/api/docs/${state.current.id}/text`);
    $("sourceText").textContent = await res.text();
    state.sourceLoadedFor = state.current.id;
  }
}

// ---------- boot ----------

document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => switchTab(t.dataset.tab)));
$("menuBtn").onclick = () => $("sidebar").classList.toggle("open");
initTheme();
initUpload();
initNotes();
initChat();
loadStatus();
loadDocs().catch((e) => toast(e.message, true));
