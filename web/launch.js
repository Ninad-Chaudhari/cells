/* The launcher: describe a task (with images if you like) and start an agent on it. */
const IDEAS = [
  ["globe", "Summarize today's top 5 stories on Hacker News, one line each"],
  ["search", "Find three open-source alternatives to Notion and compare them in a table"],
  ["book", "Read the newest arXiv abstracts about AI agents and list the key ideas"],
  ["sparkle", "Check the weekend forecast for San Francisco on weather.gov"],
];
const FILLER = new Set("a an the and or of on in for to with from by at about into my me your our this that these those it its is are be please can you".split(" "));

/* A short name from the task: "Compare the pricing pages of note apps" -> "compare-pricing-pages". */
function nameFor(task, taken) {
  const words = task.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(w => w && !FILLER.has(w));
  const base = words.slice(0, 3).join("-").slice(0, 24).replace(/-+$/, "") || "agent";
  let name = base;
  for (let i = 2; taken.has(name); i++) name = `${base}-${i}`;
  return name;
}

const Launch = {
  att: null, named: false, busy: false, runtime: store.get("cells.runtime") || "", rtKey: "",

  open() {
    $("lErr").textContent = "";
    this.renderRuntimes();
    if (!this.named) this.suggest();
    setTimeout(() => $("lTask").focus(), 30);
  },

  /* One choice per runtime the host knows; one that can't start yet says why and can't be launched. */
  renderRuntimes() {
    const rts = state.runtimes;
    if (!rts.length) return;
    if (!rts.some(r => r.id === this.runtime)) this.runtime = (rts.find(r => r.default && !r.problem) || rts.find(r => !r.problem) || rts[0]).id;
    const key = JSON.stringify([rts, this.runtime]);
    if (key === this.rtKey) return;
    this.rtKey = key;
    $("lRuntime").innerHTML = rts.map(r => `<button type="button" data-rt="${r.id}" class="${r.id === this.runtime ? "on" : ""}"${r.problem ? ` data-tip="${esc(r.problem)}" data-tip-pos="up"` : ""}>${esc(r.label)}</button>`).join("");
    $("lRuntime").querySelectorAll("button").forEach(b => b.onclick = () => {
      this.runtime = b.dataset.rt;
      store.set("cells.runtime", this.runtime);
      this.renderRuntimes();
    });
    const problem = rts.find(r => r.id === this.runtime)?.problem || "";
    $("lRtNote").textContent = problem;
    $("lStart").disabled = !!problem;
  },

  suggest() {
    $("lName").value = nameFor($("lTask").value, new Set(state.screens.map(s => s.name)));
  },

  async submit(e) {
    e.preventDefault();
    const name = $("lName").value.trim(), task = $("lTask").value.trim();
    if (!task || this.busy) return $("lTask").focus();
    this.busy = true;
    $("lStart").disabled = true;
    $("lErr").textContent = "Starting…";
    try {
      const images = await this.att.encode();
      const r = await api.post("/api/agents", { name, task, images, runtime: this.runtime });
      if (!r.ok) { $("lErr").textContent = r.message || r.error || "Couldn't start it"; return; }
      $("lErr").textContent = "";
      $("lTask").value = "";
      autosize($("lTask"), 260);
      this.att.clear();
      this.named = false;
      toast(`${name} started`, "play");
      await refreshScreens();
      go(`#/agent/${encodeURIComponent(name)}`);
    } finally {
      this.busy = false;
      this.rtKey = "";
      this.renderRuntimes();
      if (!$("lRtNote").textContent) $("lStart").disabled = false;
    }
  },

  bind() {
    this.att = new Attachments({ list: $("lAttachments"), pick: $("lAttach"), input: $("lFile"), drop: $("launchForm"),
      dropzone: $("lDrop"), paste: $("lTask") });
    $("ideas").innerHTML = IDEAS.map(([ic, text]) => `<button type="button" class="idea">${icon(ic)}<span>${esc(text)}</span></button>`).join("");
    $("ideas").querySelectorAll(".idea").forEach(b => b.onclick = () => {
      $("lTask").value = b.textContent;
      autosize($("lTask"), 260);
      if (!this.named) this.suggest();
      $("lTask").focus();
    });
    $("lTask").addEventListener("input", () => { autosize($("lTask"), 260); if (!this.named) this.suggest(); });
    $("lTask").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) $("launchForm").requestSubmit(); });
    $("lName").addEventListener("input", () => {
      this.named = !!$("lName").value;
      $("lName").value = $("lName").value.toLowerCase().replace(/[^a-z0-9-]/g, "-");
    });
    $("launchForm").addEventListener("submit", e => this.submit(e));
  },
};
