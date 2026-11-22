/* Renders an agent's activity (live or archived) as a chat. Tool calls between two messages fold into one
   "N steps" group; the group the agent is in right now stays open. */
const TOOL_NAMES = {
  browser_navigate: ["Open page", "globe"], browser_navigate_back: ["Go back", "globe"], browser_click: ["Click", "cursor"],
  browser_type: ["Type", "keyboard"], browser_press_key: ["Press key", "keyboard"], browser_snapshot: ["Read page", "eye"],
  browser_take_screenshot: ["Screenshot", "eye"], browser_evaluate: ["Run script", "bolt"], browser_tabs: ["Tabs", "globe"],
  browser_wait_for: ["Wait", "hourglass"], browser_fill_form: ["Fill form", "keyboard"], browser_select_option: ["Select", "cursor"],
  browser_hover: ["Hover", "cursor"], Bash: ["Shell", "terminal"], Read: ["Read file", "file"], Write: ["Write file", "file"],
  Edit: ["Edit file", "file"], Grep: ["Search files", "search"], Glob: ["Find files", "search"], WebFetch: ["Fetch", "globe"],
  WebSearch: ["Web search", "search"], ToolSearch: ["Load tools", "sparkle"], TodoWrite: ["Plan", "check"],
  mcp__opencontext__oc_list_folders: ["Knowledge: folders", "book"], mcp__opencontext__oc_list_docs: ["Knowledge: docs", "book"],
  mcp__opencontext__oc_create_doc: ["Knowledge: new doc", "book"], mcp__opencontext__oc_manifest: ["Knowledge: manifest", "book"],
};

function describeTool(raw, info) {
  info = info && typeof info === "object" ? info : {};
  let [label, ic] = TOOL_NAMES[raw] || [raw.replace(/^mcp__\w+?__/, "").replace(/_/g, " "), "bolt"];
  const summary = tidyPath(String(info.summary || "").replace(/\s+/g, " "));
  if (raw === "Bash" && /^need-help\b/.test(summary)) { label = "Asked for help"; ic = "alert"; }
  let args = info.args || "";
  try { args = JSON.stringify(JSON.parse(args), null, 2); } catch (e) {}
  return { raw, label, ic, summary, args: args === "{}" ? "" : args };
}

const stepHTML = (cls, ic, label, arg, detail) =>
  `<div class="step ${cls}"><div class="row"><span class="ic">${icon(ic)}</span><span class="label">${esc(label)}</span><span class="arg">${esc(arg)}</span><span class="ok"></span></div><div class="detail">${detail}</div></div>`;

class Feed {
  constructor(el, { agentName = "agent", fileUrl = rel => rel, live = false } = {}) {
    this.el = el;
    this.agentName = agentName;
    this.fileUrl = fileUrl;
    this.live = live;
    this.reset();
  }

  reset() {
    this.el.innerHTML = `<div class="feed-empty">Nothing yet.</div>`;
    this.pending = [];
    this.group = null;
    this.lastSay = null;
  }

  add([kind, text, extra]) {
    if (this.el.firstElementChild?.classList.contains("feed-empty")) this.el.textContent = "";
    if (kind === "tool") return this.tool(text, extra);
    if (kind === "result" || kind === "error") return this.pending.length ? this.output(kind, text) : this.orphan(kind, text);
    this.closeGroup();
    const say = this.lastSay;
    this.lastSay = null;
    if (kind === "you") return this.you(text, extra || {});
    if (kind === "done") {
      if (extra?.echo && say) say.remove();
      return this.append(`<div class="result"><div class="rh">${icon("check")}Done</div><div class="prose">${md(text)}</div></div>`);
    }
    if (kind === "say") this.lastSay = this.append(`<div class="agent-msg prose">${md(text)}</div>`);
  }

  /* Older entries go above what is shown; they are rendered on their own so live state is untouched. */
  prepend(entries) {
    const box = document.createElement("div");
    const older = new Feed(box, { agentName: this.agentName, fileUrl: this.fileUrl });
    for (const e of entries) older.add(e);
    older.closeGroup();
    if (!box.firstElementChild?.classList.contains("feed-empty")) this.el.prepend(...box.children);
  }

  append(html) {
    this.el.insertAdjacentHTML("beforeend", html);
    return this.el.lastElementChild;
  }

  openGroup() {
    if (this.group) return this.group;
    const el = this.append(`<div class="steps${this.live ? " open live" : ""}"><button class="steps-h"><span class="sp"></span><span class="sum"></span><span class="cnt"></span>${icon("chev")}</button><div class="steps-b"></div></div>`);
    el.querySelector(".steps-h").onclick = () => el.classList.toggle("open");
    this.group = { el, body: el.querySelector(".steps-b"), n: 0, errs: 0, labels: [] };
    return this.group;
  }

  closeGroup() {
    const g = this.group;
    this.pending = [];
    if (!g) return;
    this.group = null;
    g.el.classList.remove("live");
    if (!g.errs) g.el.classList.remove("open");
    this.summarize(g);
  }

  summarize(g) {
    const live = g.el.classList.contains("live");
    const uniq = [...new Set(g.labels)];
    g.el.querySelector(".sum").textContent = live ? `Working · ${g.labels[g.labels.length - 1] || ""}` : uniq.slice(0, 3).join(", ") + (uniq.length > 3 ? ", …" : "");
    g.el.querySelector(".cnt").textContent = `${g.n} step${g.n === 1 ? "" : "s"}${g.errs ? ` · ${g.errs} failed` : ""}`;
    g.el.classList.toggle("has-err", g.errs > 0);
  }

  addStep(g, html, label) {
    g.body.insertAdjacentHTML("beforeend", html);
    const step = g.body.lastElementChild;
    step.querySelector(".row").onclick = () => step.classList.toggle("open");
    g.n++;
    g.labels.push(label);
    this.summarize(g);
    return step;
  }

  tool(raw, info) {
    this.lastSay = null;
    const d = describeTool(raw, info);
    this.pending.push(this.addStep(this.openGroup(), stepHTML("wait", d.ic, d.label, d.summary, `<b>${esc(d.raw)}</b>${esc(d.args)}`), d.label));
  }

  output(kind, text) {
    const step = this.pending.shift();
    step.classList.remove("wait");
    step.classList.add(kind === "error" ? "err" : "done");
    step.querySelector(".detail").insertAdjacentHTML("beforeend", `\n\n<b>${kind === "error" ? "Error" : "Output"}</b>${esc(text)}`);
    if (kind === "error") { step.classList.add("open"); this.group.errs++; this.summarize(this.group); }
  }

  orphan(kind, text) {
    const err = kind === "error", g = this.openGroup();
    this.addStep(g, stepHTML(err ? "err open" : "done", err ? "x" : "file", err ? "Error" : "Output", text, esc(text)), err ? "Error" : "Output");
    if (err) { g.errs++; this.summarize(g); }
  }

  you(text, { via, images = [] }) {
    const imgs = images.map(rel => `<a href="${esc(this.fileUrl(rel))}" target="_blank" rel="noopener"><img src="${esc(this.fileUrl(rel))}" alt="" loading="lazy"></a>`).join("");
    const when = via === "during-task" ? `${icon("hourglass")}reached it mid-task` : via === "new-turn" ? `${icon("reply")}started a new turn` : "";
    this.append(`<div class="you">${imgs ? `<div class="imgs">${imgs}</div>` : ""}${text ? `<div class="bubble">${esc(text)}</div>` : ""}${when ? `<div class="meta">${when}</div>` : ""}</div>`);
  }
}
