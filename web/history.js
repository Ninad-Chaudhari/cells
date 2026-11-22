/* History: every stopped agent is archived. Browse, search, replay its chat, open its files, delete one or all. */
function runState(status) {
  const v = status || "stopped";
  if (v === "finished") return { label: "Done", dot: "green" };
  if (v.startsWith("failed")) return { label: "Failed", dot: "rose" };
  if (v === "stopped") return { label: "Stopped", dot: "" };
  return { label: v, dot: "" };
}

const History = {
  runs: [], q: "", key: "", sel: null,

  async load() {
    try {
      const d = await api.poll("/api/history");
      if (!d) return;
      this.runs = d.runs;
      $("nHistory").textContent = d.runs.length;
      const key = JSON.stringify(d.runs.map(r => [r.id, r.status]));
      if (key !== this.key) {
        this.key = key;
        if (state.route.view === "history") { this.renderList(); if (!state.route.id) this.overview(); }
      }
    } catch (e) {}
  },

  filtered() {
    const q = this.q.toLowerCase();
    if (!q) return this.runs;
    return this.runs.filter(r => [r.name, r.task].some(v => String(v || "").toLowerCase().includes(q)));
  },

  renderList() {
    const list = this.filtered(), box = $("hlist"), top = box.scrollTop;
    $("hcount").textContent = this.q ? `${list.length} of ${this.runs.length}` : `${this.runs.length} run${this.runs.length === 1 ? "" : "s"}`;
    $("hclear").disabled = !this.runs.length;
    let html = "", day = "";
    for (const r of list) {
      const d = new Date((r.ended || r.started || 0) * 1000).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
      if (d !== day) { day = d; html += `<div class="fold">${esc(d)}</div>`; }
      const x = runState(r.status);
      html += `<div class="item ${this.sel === r.id ? "on" : ""}" data-id="${esc(r.id)}">${avatar(`cell ${r.name}`)}<div class="body">
        <div class="t">${esc(r.name)}</div>
        <div class="m"><span class="dot ${x.dot}"></span>${esc(x.label)} · ${esc(runtimeLabel(r.runtime))}${r.started && r.ended ? ` · ${dur(r.ended - r.started)}` : ""}${r.ended ? ` · ${ago(r.ended)}` : ""}</div>
        <div class="d">${esc(plain(r.task))}</div></div></div>`;
    }
    box.innerHTML = html || `<div class="feed-empty">${this.runs.length ? "No matches" : "Stopped agents are archived here."}</div>`;
    box.scrollTop = top;
    box.querySelectorAll("[data-id]").forEach(e => e.onclick = () => go(`#/history/${encodeURIComponent(e.dataset.id)}`));
  },

  overview() {
    this.sel = null;
    const n = f => this.runs.filter(f).length;
    $("hmain").innerHTML = `<div class="statsgrid">
        <div class="statcard"><div class="v">${this.runs.length}</div><div class="l">Archived runs</div></div>
        <div class="statcard"><div class="v">${n(r => r.status === "finished")}</div><div class="l">Done</div></div>
        <div class="statcard"><div class="v">${n(r => r.status === "stopped")}</div><div class="l">Stopped</div></div>
        <div class="statcard"><div class="v">${n(r => String(r.status).startsWith("failed"))}</div><div class="l">Failed</div></div>
      </div>
      <div class="card doc"><div class="feed-empty">${this.runs.length ? "Pick a run to replay its chat, result and files." : "Nothing archived yet. When you stop an agent, its chat, result and files are kept here."}</div></div>`;
  },

  async show(id) {
    this.sel = id;
    this.renderList();
    let r;
    try { r = await api.get(`/api/history/${encodeURIComponent(id)}`); }
    catch (e) { $("hmain").innerHTML = `<div class="card doc"><div class="feed-empty">That run is gone.</div></div>`; return; }
    if (this.sel !== id) return;
    const x = runState(r.status);
    const url = rel => `/api/history/${encodeURIComponent(id)}/home/${rel.split("/").map(encodeURIComponent).join("/")}`;
    const files = r.files.map(f => `<a class="file" href="${url(f.path)}" target="_blank" rel="noopener">${icon("file")}<span class="p">${esc(f.path)}</span><span style="color:var(--faint)">${bytes(f.size)}</span></a>`).join("");
    $("hmain").innerHTML = `<div class="card doc">
      <div class="run-head">${avatar(`cell ${r.name}`)}<h1>${esc(r.name)}</h1><span class="status"><span class="dot ${x.dot}"></span>${esc(x.label)}</span><span class="chip-rt ${esc(r.runtime)}">${esc(runtimeLabel(r.runtime))}</span>
        <span class="grow"></span><button class="btn danger sm" id="hdel">${icon("trash")}<span id="hdelLabel">Delete</span></button></div>
      <div class="metarow" style="margin-top:10px">${r.started ? `<span>${new Date(r.started * 1000).toLocaleString()}</span>` : ""}${r.started && r.ended ? `<span>ran ${dur(r.ended - r.started)}</span>` : ""}<span class="hash">${esc(r.id)}</span></div>
      <div class="section-t">Task</div><div class="prose">${md(r.task || "—")}</div>
      ${r.result ? `<div class="section-t">Result</div><div class="result"><div class="prose">${md(r.result)}</div></div>` : ""}
      ${files ? `<div class="section-t">Files it left · ${r.files.length}</div><div class="files">${files}</div>` : ""}
      <div class="section-t">Chat</div><div class="run-feed"><div class="more ${r.start ? "" : "hidden"}" id="hmore"><button class="btn sm">Load earlier</button></div><div class="feed" id="hfeed"></div></div>
    </div>`;
    const feed = new Feed($("hfeed"), { agentName: r.name, fileUrl: rel => `/api/history/${encodeURIComponent(id)}/file/${rel}` });
    r.entries.forEach((e, i) => feed.add(e, r.start + i));
    feed.closeGroup();
    let start = r.start;
    $("hmore").querySelector("button").onclick = async () => {
      const page = await api.get(`/api/history/${encodeURIComponent(id)}/log?before=${start}`);
      if (this.sel !== id) return;
      feed.prepend(page.entries, page.start);
      start = page.start;
      $("hmore").classList.toggle("hidden", !start);
    };
    $("hdel").onclick = () => armThenRun($("hdel"), () => this.remove(id), $("hdelLabel"), ["Delete", "Delete forever?"]);
  },

  async remove(id) {
    const r = await api.post(`/api/history/${encodeURIComponent(id)}/delete`);
    if (!r.ok) return toast("Couldn't delete it", "x");
    toast("Run deleted", "trash");
    this.runs = this.runs.filter(x => x.id !== id);
    this.key = JSON.stringify(this.runs.map(r => [r.id, r.status]));
    $("nHistory").textContent = this.runs.length;
    go("#/history");
  },

  async clearAll() {
    const r = await api.post("/api/history/clear");
    if (!r.ok) return toast("Couldn't clear history", "x");
    toast(`Deleted ${r.deleted} run${r.deleted === 1 ? "" : "s"}`, "trash");
    this.runs = [];
    this.key = "";
    delete api.etags["/api/history"];
    $("nHistory").textContent = 0;
    go("#/history");
    this.load();
  },

  bind() {
    $("hq").addEventListener("input", () => { this.q = $("hq").value.trim(); this.renderList(); });
    $("hclear").onclick = () => armThenRun($("hclear"), () => this.clearAll(), $("hclearLabel"), ["Clear all", `Delete all ${this.runs.length}?`]);
  },
};
