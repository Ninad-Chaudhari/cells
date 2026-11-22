/* Knowledge: the shared Markdown base agents read and write. Docs by folder, every change as a commit with its diff. */
const Knowledge = {
  tree: null, commits: null, mode: "docs", q: "", results: null, sel: null, timer: null,

  async load() {
    try {
      const [tree, c] = await Promise.all([api.poll("/api/kb/tree"), api.poll("/api/kb/commits")]);
      if (!tree && !c) return;
      if (tree) this.tree = tree;
      if (c) this.commits = c.commits;
      $("nKb").textContent = this.tree.docs.length;
      if (state.route.view === "kb") { this.renderList(); if (!state.route.doc && !state.route.commit) this.overview(); }
    } catch (e) {}
  },

  on(type, id) { return this.sel && this.sel.type === type && this.sel.id === id ? "on" : ""; },

  renderList() {
    const box = $("kblist"), top = box.scrollTop;
    document.querySelectorAll("#kbseg button").forEach(b => b.classList.toggle("on", b.dataset.k === this.mode));
    if (!this.tree) { box.innerHTML = ""; return; }
    let html = "";
    if (this.q && this.results) {
      const re = new RegExp(this.q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "ig");
      html = `<div class="fold">Results <span class="c">${this.results.length}</span></div>` + (this.results.length ? this.results.map(r =>
        `<div class="item ${this.on("doc", r.path)}" data-doc="${esc(r.path)}"><div class="body"><div class="t">${esc(r.title)}</div><div class="m mono">${esc(r.path)}</div>${r.hits.map(h => `<div class="hit">${esc(h).replace(re, m => `<mark>${m}</mark>`)}</div>`).join("")}</div></div>`).join("")
        : `<div class="feed-empty">No matches</div>`);
    } else if (this.mode === "docs") {
      const byFolder = new Map();
      for (const f of this.tree.folders) byFolder.set(f.path, { f, docs: [] });
      for (const d of this.tree.docs) {
        if (!byFolder.has(d.folder)) byFolder.set(d.folder, { f: { path: d.folder }, docs: [] });
        byFolder.get(d.folder).docs.push(d);
      }
      for (const { f, docs } of byFolder.values()) {
        if (f.path.includes("/") && !docs.length) continue;
        html += `<div class="fold" ${f.description ? `data-tip="${esc(f.description)}"` : ""}>${esc(f.path || "root")}<span class="c">${docs.length}</span></div>`;
        html += docs.length ? docs.map(d => `<div class="item ${this.on("doc", d.path)}" data-doc="${esc(d.path)}"><div class="body"><div class="t">${esc(d.title)}</div><div class="m">${d.last ? `${avatar(d.last.author, true)}${esc(who(d.last.author).name)} · ${ago(d.last.at)}` : `edited ${ago(d.mtime)}`}${d.dirty ? `<span class="tag dirty">unsaved</span>` : ""}</div></div></div>`).join("")
          : `<div class="item" style="cursor:default"><div class="m" style="margin:0">Empty</div></div>`;
      }
      if (!html) html = `<div class="feed-empty">No docs yet. Agents add what they learn here.</div>`;
    } else {
      html = (this.commits || []).map(c => {
        const files = c.files.filter(f => f.path.startsWith("contexts/"));
        const add = files.reduce((a, f) => a + (f.adds || 0), 0), del = files.reduce((a, f) => a + (f.dels || 0), 0);
        return `<div class="item ${this.on("commit", c.hash)}" data-commit="${c.hash}">${avatar(c.author)}<div class="body"><div class="t">${esc(c.subject)}</div><div class="m">${esc(who(c.author).name)} · ${ago(c.at)} · <span class="plus-n">+${add}</span> <span class="minus">−${del}</span></div></div></div>`;
      }).join("") || `<div class="feed-empty">No changes yet</div>`;
    }
    box.innerHTML = html;
    box.scrollTop = top;
    box.querySelectorAll("[data-doc]").forEach(e => e.onclick = () => go(`#/knowledge/doc/${encodeURIComponent(e.dataset.doc)}`));
    box.querySelectorAll("[data-commit]").forEach(e => e.onclick = () => go(`#/knowledge/commit/${e.dataset.commit}`));
  },

  timeline(list, withHash) {
    return list.map(c => `<div class="tl-row" data-commit="${c.hash}">${avatar(c.author)}<span class="s">${esc(c.subject)}</span>${withHash ? `<span class="hash">${c.hash}</span>` : ""}<span class="w">${ago(c.at)}</span></div>`).join("");
  },

  linkCommits() {
    $("kbmain").querySelectorAll("[data-commit]").forEach(e => e.onclick = () => go(`#/knowledge/commit/${e.dataset.commit}`));
  },

  overview() {
    this.sel = null;
    if (!this.tree) return;
    const counts = new Map();
    for (const c of this.commits || []) counts.set(c.author, (counts.get(c.author) || 0) + 1);
    const contrib = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...contrib.map(c => c[1]));
    $("kbmain").innerHTML = `
      <div class="statsgrid">
        <div class="statcard"><div class="v">${this.tree.docs.length}</div><div class="l">Docs</div></div>
        <div class="statcard"><div class="v">${this.tree.folders.length}</div><div class="l">Folders</div></div>
        <div class="statcard"><div class="v">${this.tree.commits}</div><div class="l">Changes</div></div>
        <div class="statcard"><div class="v">${contrib.length}</div><div class="l">Contributors</div></div>
      </div>
      <div class="two">
        <div class="card panel"><h3>Recent changes</h3><div class="timeline">${this.timeline((this.commits || []).slice(0, 6)) || `<div class="feed-empty">Nothing yet</div>`}</div></div>
        <div class="card panel"><h3>Contributors</h3>${contrib.map(([a, n]) => `<div class="contrib">${avatar(a)}<span class="n">${esc(who(a).name)}</span><span class="bar" style="width:${Math.round(90 * n / max)}px"></span><span class="mono" style="color:var(--faint);font-size:12px;width:24px;text-align:right">${n}</span></div>`).join("") || `<div class="feed-empty">Nobody yet</div>`}</div>
      </div>`;
    this.linkCommits();
  },

  async showDoc(path) {
    this.sel = { type: "doc", id: path };
    this.renderList();
    let d;
    try { d = await api.get(`/api/kb/doc?path=${encodeURIComponent(path)}`); }
    catch (e) { $("kbmain").innerHTML = `<div class="card doc"><div class="feed-empty">That doc no longer exists.</div></div>`; return; }
    const meta = this.tree?.docs.find(x => x.path === path);
    const last = d.history[0];
    const crumbs = path.split("/");
    $("kbmain").innerHTML = `<div class="card doc">
      <div class="crumbs">${crumbs.map((c, i) => `<span>${esc(c)}</span>${i < crumbs.length - 1 ? "<span>/</span>" : ""}`).join("")}</div>
      <h1 class="title">${esc(d.title)}</h1>
      <div class="metarow">${last ? `<span class="who">${avatar(last.author, true)}${esc(who(last.author).name)} · ${ago(last.at)}</span>` : ""}<span>${d.history.length} change${d.history.length === 1 ? "" : "s"}</span>${meta?.dirty ? `<span class="tag dirty">unsaved edits</span>` : ""}</div>
      ${d.description ? `<p class="desc">${esc(d.description)}</p>` : ""}
      <div class="prose">${md(d.content.replace(/^\s*#\s+(.+)\n?/, (m, t) => t.trim() === d.title ? "" : m))}</div>
      ${d.history.length ? `<div class="section-t">History</div><div class="timeline">${this.timeline(d.history, true)}</div>` : ""}
    </div>`;
    this.linkCommits();
  },

  async showCommit(hash) {
    this.sel = { type: "commit", id: hash };
    this.mode = "changes";
    this.renderList();
    let c;
    try { c = await api.get(`/api/kb/commit?hash=${encodeURIComponent(hash)}`); }
    catch (e) { $("kbmain").innerHTML = `<div class="card doc"><div class="feed-empty">Change not found.</div></div>`; return; }
    const files = c.files.map(f => `<div class="file">${icon(f.path.endsWith(".db") ? "sparkle" : "file")}<span class="p">${esc(f.path.replace(/^contexts\//, ""))}${f.path.endsWith(".db") ? ` <span style="color:var(--faint)">· search index</span>` : ""}</span>${f.adds == null ? `<span style="color:var(--faint)">binary</span>` : `<span class="plus-n">+${f.adds}</span><span class="minus">−${f.dels}</span>`}</div>`).join("");
    $("kbmain").innerHTML = `<div class="card doc">
      <div class="metarow"><span class="who">${avatar(c.author)}<b style="color:var(--text)">${esc(who(c.author).name)}</b></span><span>${ago(c.at)}</span><span class="hash">${c.hash}</span></div>
      <h1 class="title" style="font-size:20px">${esc(c.subject)}</h1>
      ${c.body ? `<p class="desc">${esc(c.body)}</p>` : ""}
      <div class="files">${files}</div>
      ${this.diff(c.diff)}
    </div>`;
  },

  diff(text) {
    if (!text.trim()) return "";
    return text.split(/^diff --git /m).filter(Boolean).map(chunk => {
      const lines = chunk.split("\n");
      const m = lines[0].match(/ b\/(.+)$/);
      const name = m ? m[1].replace(/^contexts\//, "") : lines[0];
      const body = lines.slice(1).filter(l => !/^(index |new file mode|deleted file mode|--- |\+\+\+ |similarity|rename )/.test(l));
      return `<div class="diff"><div class="fh">${esc(name)}</div><pre>${body.map(l => {
        const cls = l.startsWith("@@") ? "hunk" : l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : "";
        return `<span class="ln ${cls}">${esc(l) || " "}</span>`;
      }).join("")}</pre></div>`;
    }).join("");
  },

  bind() {
    $("kbq").addEventListener("input", () => {
      this.q = $("kbq").value.trim();
      clearTimeout(this.timer);
      if (!this.q) { this.results = null; this.renderList(); return; }
      this.timer = setTimeout(async () => {
        const q = this.q;
        try {
          const r = await api.get(`/api/kb/search?q=${encodeURIComponent(q)}`);
          if (q === this.q) { this.results = r.results; this.renderList(); }
        } catch (e) {}
      }, 180);
    });
    document.querySelectorAll("#kbseg button").forEach(b => b.onclick = () => { this.mode = b.dataset.k; this.renderList(); });
  },
};
