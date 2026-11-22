/* Agents: header stats, the grid of live screens, the focused agent view, and the New agent dialog. */
const state = { screens: [], host: "", route: { view: "agents" } };

function agentState(s) {
  if (!s.agent) return { key: "screen", label: "Screen", dot: "" };
  if (s.help) return { key: "help", label: "Needs you", dot: "amber pulse" };
  if (s.paused) return { key: "paused", label: "Paused", dot: "blue" };
  const v = s.status || "starting";
  if (v === "running") return { key: "running", label: "Working", dot: "green pulse" };
  if (v === "starting") return { key: "running", label: "Starting", dot: "green pulse" };
  if (v === "idle") return { key: "idle", label: "Waiting", dot: "violet" };
  if (v === "finished") return { key: "finished", label: "Done", dot: "" };
  if (v === "stopped") return { key: "finished", label: "Stopped", dot: "" };
  if (v.startsWith("failed")) return { key: "failed", label: "Failed", dot: "rose" };
  return { key: "finished", label: v, dot: "" };
}
const ended = s => s.agent && s.status && !["starting", "running", "idle"].includes(s.status);
const chattable = s => s.agent && ["starting", "running", "idle"].includes(s.status || "starting");
const statusHTML = s => { const x = agentState(s); return `<span class="dot ${x.dot}"></span>${esc(x.label)}`; };

async function refreshScreens() {
  try {
    const data = await api.poll("/api/state");
    if (data) {
      clock.offset = data.now - Date.now() / 1000;
      state.screens = data.screens;
      if (state.host !== data.host) { state.host = data.host; $("hostLabel").textContent = `OS for agents · ${data.host}`; }
      renderHeader();
      if (state.route.view === "agents") renderGrid();
      if (state.route.view === "agent") Focus.update();
    }
    $("live").querySelector(".dot").className = "dot green";
    $("liveText").textContent = "Live";
  } catch (e) {
    $("live").querySelector(".dot").className = "dot rose";
    $("liveText").textContent = "Offline";
  }
}

function renderHeader() {
  const a = state.screens.filter(s => s.agent);
  const c = f => a.filter(f).length;
  const working = c(s => !ended(s) && !s.help && !s.paused && s.status !== "idle");
  const help = c(s => s.help), waiting = c(s => s.status === "idle" && !s.help), paused = c(s => s.paused && !s.help);
  const parts = [`<span class="stat"><span class="dot green ${working ? "pulse" : ""}"></span><b>${working}</b>working</span>`];
  if (help) parts.push(`<span class="stat warn"><span class="dot amber pulse"></span><b>${help}</b>need${help === 1 ? "s" : ""} you</span>`);
  if (waiting) parts.push(`<span class="stat"><span class="dot violet"></span><b>${waiting}</b>waiting</span>`);
  if (paused) parts.push(`<span class="stat"><span class="dot blue"></span><b>${paused}</b>paused</span>`);
  $("stats").innerHTML = parts.join("");
  $("nAgents").textContent = state.screens.length;
  document.title = help ? `(${help}) Cells` : "Cells";
}

/* grid: each tile pulls a preview sized to how big it is drawn, only while it is on screen */
const tiles = new Map();
const seen = new IntersectionObserver(list => {
  for (const e of list) { const t = tiles.get(e.target.dataset.name); if (t) t.visible = e.isIntersecting; }
}, { rootMargin: "200px" });
function addTile(s) {
  const el = document.createElement("article");
  el.className = "tile";
  el.innerHTML = `<img class="shot hidden" alt=""><div class="ph">Connecting…</div><div class="veil"></div>
    <div class="pill glass tl"><span class="dot"></span><span class="nm"></span><span class="sep"></span><span class="st"></span></div>
    <div class="acts"><button class="kill glass" title="Stop this session">${icon("stop")}<span class="kl">Stop?</span></button><div class="pill glass tr"></div></div>
    <div class="pill glass bl"><span class="bi"></span><span class="bt"></span></div>`;
  el.querySelector(".nm").textContent = s.name;
  el.dataset.name = s.name;
  el.addEventListener("click", () => go(`#/agent/${encodeURIComponent(s.name)}`));
  const kill = el.querySelector(".kill");
  kill.addEventListener("click", e => { e.stopPropagation(); armThenRun(kill, () => stopSession(s.name)); });
  $("grid").appendChild(el);
  seen.observe(el);
  tiles.set(s.name, { el, busy: false, visible: true, etag: "", url: "", img: el.querySelector(".shot"), ph: el.querySelector(".ph"),
    dot: el.querySelector(".tl .dot"), st: el.querySelector(".tl .st"), tr: el.querySelector(".tr"),
    bl: el.querySelector(".bl"), bi: el.querySelector(".bi"), bt: el.querySelector(".bt") });
}
function updateTile(s) {
  const t = tiles.get(s.name), x = agentState(s);
  t.el.classList.toggle("is-help", !!s.help);
  t.el.classList.toggle("is-ended", ended(s));
  t.el.classList.toggle("is-failed", x.key === "failed");
  t.el.classList.toggle("is-stopping", !!s.stopping);
  t.dot.className = `dot ${x.dot}`;
  t.st.textContent = x.label;
  t.tr.title = `Screen ${s.display}`;
  let ic = "", text = s.task || (s.agent ? "" : "Plain screen");
  if (s.help) { ic = "alert"; text = s.help.message; }
  else if (ended(s)) { ic = x.key === "failed" ? "x" : "check"; text = plain(s.result) || x.label; }
  if (t.bi.dataset.ic !== ic) { t.bi.innerHTML = ic ? icon(ic) : ""; t.bi.dataset.ic = ic; }
  t.bt.textContent = text;
  t.bl.classList.toggle("hidden", !text);
}
function renderGrid() {
  const names = state.screens.map(s => s.name);
  for (const s of state.screens) { if (!tiles.has(s.name)) addTile(s); updateTile(s); }
  for (const [n, t] of tiles) if (!names.includes(n)) { seen.unobserve(t.el); if (t.url) URL.revokeObjectURL(t.url); t.el.remove(); tiles.delete(n); }
  $("empty").classList.toggle("hidden", names.length > 0);
  renderHelpStrip();
}
let helpKey = "";
function renderHelpStrip() {
  const list = state.screens.filter(s => s.help);
  $("helpstrip").classList.toggle("hidden", !list.length);
  const key = JSON.stringify(list.map(s => [s.name, s.help.message, s.help.at]));
  if (key !== helpKey) {
    helpKey = key;
    $("helpstrip").innerHTML = `<span class="lead">${icon("alert")}${list.length === 1 ? "1 agent needs you" : `${list.length} agents need you`}</span>` +
      list.map(s => `<div class="hcard" data-go="${esc(s.name)}"><span class="who">${esc(s.name)}</span><span class="msg">${esc(s.help.message)}</span><span class="ago" data-at="${s.help.at || ""}"></span></div>`).join("");
    $("helpstrip").querySelectorAll("[data-go]").forEach(c => c.onclick = () => go(`#/agent/${encodeURIComponent(c.dataset.go)}`));
  }
  $("helpstrip").querySelectorAll(".ago").forEach(e => { const a = Number(e.dataset.at); e.textContent = a ? dur(now() - a) : ""; });
}
/* Readable but light: the tile's drawn width in device pixels, never under 640 px. */
const previewWidth = el => Math.min(1920, Math.max(640, Math.ceil(el.clientWidth * (window.devicePixelRatio || 1) / 160) * 160));
async function refreshTile(name, t) {
  t.busy = true;
  try {
    const r = await fetch(`/shot/${encodeURIComponent(name)}?w=${previewWidth(t.el)}`,
      { cache: "no-store", headers: t.etag ? { "If-None-Match": t.etag } : {} });
    if (r.status !== 200) return;
    t.etag = r.headers.get("ETag") || "";
    const url = URL.createObjectURL(await r.blob());
    await new Promise(done => { t.img.onload = t.img.onerror = done; t.img.src = url; });
    if (t.url) URL.revokeObjectURL(t.url);
    t.url = url;
    t.img.classList.remove("hidden");
    t.ph.classList.add("hidden");
  } catch (e) {
  } finally {
    t.busy = false;
  }
}
function refreshShots() {
  if (document.hidden || state.route.view !== "agents") return;
  for (const [n, t] of tiles) if (t.visible && !t.busy) refreshTile(n, t);
}
async function stopSession(name) {
  const r = await api.post(`/stop/${encodeURIComponent(name)}`);
  if (!r.ok) return toast("Couldn't stop it", "x");
  toast(`Stopping ${name} · history kept`, "stop");
  tiles.get(name)?.el.classList.add("is-stopping");
  if (state.route.view === "agent" && Focus.name === name) go("#/agents");
  refreshScreens();
}

/* focused agent */
const Focus = {
  name: null, current: {}, control: false, autoPaused: false, logNext: null, logStart: 0, logBusy: false, feed: null,

  open(name) {
    if (this.name === name) return;
    if (this.name && this.control) this.setControl(false);
    this.name = name;
    this.logNext = null;
    this.feed = new Feed($("feed"), { agentName: name, fileUrl: rel => `/file/${encodeURIComponent(name)}/${rel}`, live: true });
    $("jump").classList.add("hidden");
    $("more").classList.add("hidden");
    $("fname").textContent = name;
    this.control = false; this.autoPaused = false; this.drawControl();
    showSideTab("activity");
    Chat.reset();
    this.update(); this.refreshLog(); window.scrollTo(0, 0);
  },

  async close() {
    if (this.control) await this.setControl(false);
    this.name = null;
    this.stream();
  },

  /* The watched screen streams at native resolution, faster while you drive it, and not at all when it isn't visible. */
  stream() {
    const fps = this.control ? 12 : 5;
    const shown = this.name && !document.hidden && Layout.mode !== "chat";
    const want = shown ? `/stream/${encodeURIComponent(this.name)}?fps=${fps}` : "";
    if ($("fimg").dataset.src === want) return;
    $("fimg").dataset.src = want;
    if (want) $("fimg").src = want; else $("fimg").removeAttribute("src");
  },

  update() {
    const s = state.screens.find(x => x.name === this.name);
    this.current = s || {};
    if (!s) { $("fstatus").innerHTML = `<span class="dot"></span>Gone`; Chat.setEnabled(false, "This agent is gone"); return; }
    $("fstatus").innerHTML = statusHTML(s);
    $("fmeta").textContent = s.started ? `${dur(now() - s.started)} · ${s.display}` : s.display;
    $("fhelp").classList.toggle("hidden", !s.help);
    if (s.help) $("fhelpmsg").textContent = s.help.message;
    $("pause").classList.toggle("hidden", !s.agent || ended(s) || s.status === "idle");
    $("pause").innerHTML = s.paused ? icon("play") + "Resume" : icon("pause") + "Pause";
    $("stageIdle").classList.toggle("hidden", !ended(s));
    if (ended(s)) $("stageIdle").innerHTML = `<div>${icon(agentState(s).key === "failed" ? "x" : "check")}<span>${esc(agentState(s).label)} · browser closed</span></div>`;
    if ($("ttask").dataset.v !== (s.task || "")) { $("ttask").dataset.v = s.task || ""; $("ttask").innerHTML = md(s.task || "—"); }
    $("tstarted").textContent = s.started ? new Date(s.started * 1000).toLocaleString() : "—";
    $("tresultWrap").classList.toggle("hidden", !s.result);
    if ($("tresult").dataset.v !== (s.result || "")) { $("tresult").dataset.v = s.result || ""; $("tresult").innerHTML = md(s.result || ""); }
    Chat.update(s);
  },

  drawControl() {
    $("take").className = this.control ? "btn on" : "btn";
    $("take").innerHTML = this.control ? icon("release") + "Release" : icon("hand") + "Take over";
    $("stage").classList.toggle("control", this.control);
    this.stream();
  },

  post(action, body) { return api.post(`/${action}/${encodeURIComponent(this.name)}`, body); },

  async setControl(on) {
    if (on && Layout.mode === "chat") Layout.set("both");
    this.control = on;
    this.drawControl();
    if (on && this.current.agent && !this.current.paused && this.current.status === "running") {
      const r = await this.post("pause");
      this.autoPaused = r.ok;
      if (r.ok) toast("Agent paused · you're in control", "hand");
    } else if (!on && this.autoPaused) {
      await this.post("resume");
      this.autoPaused = false;
      toast("Released · agent resumed");
    }
    refreshScreens();
  },

  /* Opening a chat loads only its latest page; after that only what's new. Older pages load on request. */
  async refreshLog() {
    if (!this.name || document.hidden || this.logBusy || Layout.mode === "screen") return;
    const name = this.name;
    this.logBusy = true;
    try {
      const data = await api.get(`/api/log/${encodeURIComponent(name)}${this.logNext === null ? "" : `?since=${this.logNext}`}`);
      if (name !== this.name) return;
      const fresh = this.logNext === null || data.reset;
      if (fresh) {
        this.feed.reset();
        this.logStart = data.start;
        $("more").classList.toggle("hidden", !data.start);
      }
      this.logNext = data.next;
      if (!data.entries.length) return;
      const pane = $("activityPane");
      const atBottom = fresh || pane.scrollHeight - pane.scrollTop - pane.clientHeight < 80;
      for (const e of data.entries) this.feed.add(e);
      if (atBottom) pane.scrollTop = pane.scrollHeight; else $("jump").classList.remove("hidden");
    } catch (e) {
    } finally {
      this.logBusy = false;
    }
  },

  async loadEarlier() {
    const name = this.name;
    const data = await api.get(`/api/log/${encodeURIComponent(name)}?before=${this.logStart}`);
    if (name !== this.name) return;
    const pane = $("activityPane"), height = pane.scrollHeight;
    this.feed.prepend(data.entries);
    pane.scrollTop += pane.scrollHeight - height;
    this.logStart = data.start;
    $("more").classList.toggle("hidden", !data.start);
  },
};

/* What the agent page shows: screen, chat or both, split by a draggable divider. Remembered per browser. */
const SIDE_DEFAULT = 420;
const Layout = {
  mode: ["screen", "both", "chat"].includes(store.get("cells.layout")) ? store.get("cells.layout") : "both",
  side: Number(store.get("cells.side")) || SIDE_DEFAULT,

  apply() {
    $("fbody").dataset.layout = this.mode;
    $("fbody").style.setProperty("--side", `${this.side}px`);
    document.querySelectorAll("#layoutSeg button").forEach(b => b.classList.toggle("on", b.dataset.layout === this.mode));
    Focus.stream();
  },

  set(mode) {
    this.mode = mode;
    store.set("cells.layout", mode);
    this.apply();
    Focus.refreshLog();
  },

  bind() {
    document.querySelectorAll("#layoutSeg button").forEach(b => b.onclick = () => this.set(b.dataset.layout));
    const bar = $("splitter"), body = $("fbody");
    bar.addEventListener("pointerdown", e => {
      e.preventDefault();
      bar.setPointerCapture(e.pointerId);
      body.classList.add("dragging");
      const move = ev => {
        const r = body.getBoundingClientRect();
        this.side = Math.round(Math.max(340, Math.min(r.right - ev.clientX - 7, r.width - 480)));
        body.style.setProperty("--side", `${this.side}px`);
      };
      const up = () => {
        bar.removeEventListener("pointermove", move);
        bar.removeEventListener("pointerup", up);
        body.classList.remove("dragging");
        store.set("cells.side", this.side);
      };
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", up);
    });
    bar.addEventListener("dblclick", () => { this.side = SIDE_DEFAULT; store.set("cells.side", this.side); this.apply(); });
    this.apply();
  },
};

function showSideTab(tab) {
  document.querySelectorAll("#sideTabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  $("activityPane").classList.toggle("hidden", tab !== "activity");
  $("taskPane").classList.toggle("hidden", tab !== "task");
}

function point(e) {
  const img = $("fimg"), r = img.getBoundingClientRect();
  const iw = img.naturalWidth || 1280, ih = img.naturalHeight || 800, k = Math.min(r.width / iw, r.height / ih);
  const w = iw * k, h = ih * k, l = r.left + (r.width - w) / 2, t = r.top + (r.height - h) / 2;
  return { x: (e.clientX - l) / w, y: (e.clientY - t) / h };
}
const NAMED = { Enter: "Return", Backspace: "BackSpace", Tab: "Tab", Escape: "Escape", ArrowUp: "Up", ArrowDown: "Down", ArrowLeft: "Left", ArrowRight: "Right", Delete: "Delete", Home: "Home", End: "End", PageUp: "Prior", PageDown: "Next", " ": "space" };
function keyEvent(e) {
  if (["Shift", "Control", "Alt", "Meta"].includes(e.key)) return null;
  const mods = [];
  if (e.ctrlKey || e.metaKey) mods.push("ctrl");
  if (e.altKey) mods.push("alt");
  let k = NAMED[e.key];
  if (!k) {
    if (e.key.length !== 1) return null;
    if (!mods.length) return { type: "text", text: e.key };
    if (!/^[A-Za-z0-9]$/.test(e.key)) return null;
    k = e.key.toLowerCase();
  }
  if (e.shiftKey && (NAMED[e.key] || mods.length)) mods.push("shift");
  return { type: "key", keys: [...mods, k].join("+") };
}

function bindAgentControls() {
  $("back").onclick = () => go("#/agents");
  $("take").onclick = () => Focus.setControl(!Focus.control);
  $("stop").onclick = () => armThenRun($("stop"), () => stopSession(Focus.name), $("stopLabel"), ["Stop", "Confirm stop"]);
  $("pause").onclick = async () => {
    const r = Focus.current.paused;
    await Focus.post(r ? "resume" : "pause");
    Focus.autoPaused = false;
    toast(r ? "Agent resumed" : "Agent paused", r ? "play" : "pause");
    refreshScreens();
  };
  $("resolve").onclick = async () => {
    await Focus.post("resolve", { note: $("note").value });
    $("note").value = "";
    if (Focus.control) { Focus.autoPaused = false; Focus.control = false; Focus.drawControl(); }
    toast("Resumed with your note");
    refreshScreens();
  };
  $("note").addEventListener("keydown", e => { if (e.key === "Enter") $("resolve").click(); });
  $("send").onclick = () => {
    const t = $("text").value;
    if (!t) return;
    Focus.post("input", { type: "text", text: t });
    $("text").value = "";
    toast("Typed on screen", "keyboard");
  };
  $("text").addEventListener("keydown", e => { if (e.key === "Enter") $("send").click(); });
  $("fimg").addEventListener("click", e => { if (Focus.control) Focus.post("input", { type: "click", button: 1, ...point(e) }); });
  $("fimg").addEventListener("contextmenu", e => { if (Focus.control) { e.preventDefault(); Focus.post("input", { type: "click", button: 3, ...point(e) }); } });
  $("fimg").addEventListener("wheel", e => { if (Focus.control) { e.preventDefault(); Focus.post("input", { type: "scroll", dy: e.deltaY, ...point(e) }); } }, { passive: false });
  document.querySelectorAll("#sideTabs button").forEach(b => b.onclick = () => showSideTab(b.dataset.tab));
  $("jump").querySelector("button").onclick = () => { const p = $("activityPane"); p.scrollTop = p.scrollHeight; $("jump").classList.add("hidden"); };
  $("activityPane").addEventListener("scroll", () => { const p = $("activityPane"); if (p.scrollHeight - p.scrollTop - p.clientHeight < 80) $("jump").classList.add("hidden"); });
  $("more").querySelector("button").onclick = () => Focus.loadEarlier();
  $("copyCmd").onclick = async () => { try { await navigator.clipboard.writeText($("cmdText").textContent); toast("Copied"); } catch (e) {} };
}
