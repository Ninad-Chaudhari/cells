/* Routing, refresh loops and keyboard shortcuts. */
const VIEWS = { agents: "agentsView", new: "launchView", agent: "focusView", history: "historyView", kb: "kbView", metrics: "metricsView" };

function go(hash) {
  if (location.hash !== hash) location.hash = hash;
  else render();
}

function parseRoute() {
  const seg = (location.hash || "#/agents").replace(/^#\/?/, "").split("/");
  const rest = n => decodeURIComponent(seg.slice(n).join("/"));
  if (seg[0] === "new") return { view: "new" };
  if (seg[0] === "metrics") return { view: "metrics" };
  if (seg[0] === "agent" && seg[1]) return { view: "agent", name: rest(1) };
  if (seg[0] === "history") return { view: "history", id: rest(1) };
  if (seg[0] === "knowledge" && seg[1] === "doc") return { view: "kb", doc: rest(2) };
  if (seg[0] === "knowledge" && seg[1] === "commit") return { view: "kb", commit: rest(2) };
  if (seg[0] === "knowledge") return { view: "kb" };
  return { view: "agents" };
}

async function render() {
  const prev = state.route, r = parseRoute();
  state.route = r;
  for (const [v, id] of Object.entries(VIEWS)) $(id).classList.toggle("hidden", v !== r.view);
  document.body.className = `v-${r.view}`;
  const tab = r.view === "agent" || r.view === "new" ? "agents" : r.view;
  document.querySelectorAll(".nav button").forEach(b => b.classList.toggle("on", b.dataset.view === tab));
  if (prev.view === "agent" && r.view !== "agent") await Focus.close();
  if (r.view === "agent") Focus.open(r.name);
  if (r.view === "new") Launch.open();
  if (r.view === "agents") { renderGrid(); refreshShots(); }
  if (["agents", "agent", "metrics"].includes(r.view)) { Metrics.paint(); Metrics.load(); }
  if (r.view === "history") {
    History.renderList();
    if (r.id) History.show(r.id); else History.overview();
  }
  if (r.view === "kb") {
    Knowledge.renderList();
    if (r.doc) Knowledge.showDoc(r.doc);
    else if (r.commit) Knowledge.showCommit(r.commit);
    else Knowledge.overview();
  }
}

function onKey(e) {
  const typing = e.target.closest?.("input, textarea, select, [contenteditable]");
  if (state.route.view === "agent" && Focus.control && !typing) {
    const ev = keyEvent(e);
    if (ev) { e.preventDefault(); Focus.post("input", ev); }
    return;
  }
  if (e.key === "Escape") {
    if (typing && state.route.view !== "new") return e.target.blur();
    if (state.route.view === "agent" || state.route.view === "new") go("#/agents");
    return;
  }
  if (e.key === "n" && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) {
    e.preventDefault();
    go("#/new");
  }
}

function tick() {
  if (state.route.view === "agents") renderHelpStrip();
  if (state.route.view === "agent" && Focus.current.started) $("fmeta").textContent = `${dur(now() - Focus.current.started)} · ${Focus.current.display}`;
}

(async function start() {
  hydrate(document.body);
  document.querySelectorAll(".nav button").forEach(b => b.onclick = () => go(b.dataset.route));
  bindAgentControls();
  Launch.bind();
  Layout.bind();
  $("newAgent").onclick = () => go("#/new");
  $("emptyNew").onclick = () => go("#/new");
  Chat.bind();
  History.bind();
  Knowledge.bind();
  document.addEventListener("keydown", onKey);
  document.addEventListener("visibilitychange", () => {
    Focus.stream();
    if (!document.hidden) { refreshScreens(); refreshShots(); History.load(); Knowledge.load(); }
  });
  window.addEventListener("hashchange", render);

  await refreshScreens();
  render();
  History.load();
  Knowledge.load();
  setInterval(refreshScreens, 2000);
  setInterval(refreshShots, 1500);
  setInterval(() => Focus.refreshLog(), 1500);
  setInterval(() => { if (!document.hidden) { History.load(); Knowledge.load(); } }, 10000);
  setInterval(() => { if (["agents", "agent", "metrics"].includes(state.route.view)) Metrics.load(); }, 3000);
  setInterval(tick, 1000);
})();
