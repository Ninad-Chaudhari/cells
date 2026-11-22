/* Metrics: what the host and each agent use, as the server reads it from the kernel. Polled only while a
   view that shows it is open; the grid and the agent page show each agent's share too. */
const HISTORY_POINTS = 60;
const COLUMNS = [
  ["name", "Agent", false], ["status", "Status", false], ["cpu", "CPU", true], ["mem", "Memory", true],
  ["disk", "Disk", true], ["tokens", "Tokens", true], ["pids", "Processes", true], ["up", "Uptime", true],
];

const diskOf = c => c.disk ? (c.disk.home || 0) + (c.disk.state || 0) : null;
const tokensOf = c => c.tokens ? c.tokens.input + c.tokens.output : null;

function sparkline(values, max = 100) {
  if (values.length < 2) return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none"></svg>`;
  const step = 100 / (HISTORY_POINTS - 1), x0 = 100 - step * (values.length - 1);
  const pts = values.map((v, i) => `${(x0 + i * step).toFixed(2)},${(33 - Math.min(v, max) / max * 31).toFixed(2)}`);
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none"><path class="area" d="M${pts[0].split(",")[0]},34 L${pts.join(" L")} L100,34 Z"/><path class="line" d="M${pts.join(" L")}"/></svg>`;
}

const Metrics = {
  data: null, byName: {}, cpuHist: [], busy: false,
  sort: store.get("cells.msort") || "mem", dir: Number(store.get("cells.mdir")) || -1,

  async load() {
    if (this.busy || document.hidden) return;
    this.busy = true;
    try {
      const d = await api.get("/api/metrics");
      this.data = d;
      this.byName = Object.fromEntries(d.cells.map(c => [c.name, c]));
      if (d.host.cpu != null) {
        this.cpuHist.push(d.host.cpu);
        if (this.cpuHist.length > HISTORY_POINTS) this.cpuHist.shift();
      }
      this.paint();
    } catch (e) {
    } finally {
      this.busy = false;
    }
  },

  paint() {
    if (state.route.view === "metrics") this.render();
    if (state.route.view === "agents") paintTileUsage();
    if (state.route.view === "agent") Focus.paintUsage();
  },

  render() {
    if (!this.data) {
      $("glance").innerHTML = "";
      $("mtable").innerHTML = `<div class="none">Measuring…</div>`;
      return;
    }
    const h = this.data.host, cells = this.data.cells;
    const mem = h.mem, total = mem.total || 0, agents = h.cells_mem || 0;
    const other = Math.max(0, (mem.used || 0) - agents);
    const w = v => total ? `${(v / total * 100).toFixed(2)}%` : "0";
    const disk = h.disks[0];
    const running = state.screens.filter(s => s.agent && ["starting", "running", "idle"].includes(s.status)).length;
    const tok = cells.reduce((a, c) => [a[0] + (c.tokens?.input || 0), a[1] + (c.tokens?.output || 0)], [0, 0]);
    $("glance").innerHTML = `
      <div class="gcard"><div class="h">${icon("cpu")}CPU</div>
        <div class="v">${pct(h.cpu)}<small>of ${h.cores} cores</small></div>
        <div class="s">Load ${h.load.map(x => x.toFixed(2)).join(" · ")}</div>${sparkline(this.cpuHist)}</div>
      <div class="gcard"><div class="h">${icon("memory")}Memory</div>
        <div class="v">${bytes(mem.used)}<small>of ${bytes(total)}</small></div>
        <div class="meter"><i class="a" style="width:${w(agents)}"></i><i class="b" style="width:${w(other)}"></i></div>
        <div class="legend"><span><i style="background:var(--accent)"></i>Agents ${bytes(agents)}</span><span><i style="background:var(--gray)"></i>Other ${bytes(other)}</span><span>Free ${bytes(mem.available)}</span></div></div>
      <div class="gcard"><div class="h">${icon("disk")}Storage</div>
        ${disk ? `<div class="v">${bytes(disk.free)}<small>free of ${bytes(disk.total)}</small></div>
        <div class="meter"><i class="a" style="width:${(disk.used / disk.total * 100).toFixed(2)}%"></i></div>` : `<div class="v">—</div>`}
        <div class="legend"><span>History ${bytes(h.storage.history)}</span><span>Knowledge ${bytes(h.storage.knowledge)}</span>${h.disks[1] ? `<span>Cell homes ${bytes(h.disks[1].free)} free</span>` : ""}</div></div>
      <div class="gcard"><div class="h">${icon("agents")}Agents</div>
        <div class="v">${running}<small>of ${state.max || "—"}</small></div>
        <div class="s">${count(tok[0])} tokens in · ${count(tok[1])} out</div>
        <div class="s">Control plane ${bytes(h.control_plane.rss)} · ${h.control_plane.threads ?? "—"} threads</div></div>`;
    this.renderTable(cells);
  },

  value(c, key) {
    switch (key) {
      case "name": return c.name;
      case "status": return agentState(state.screens.find(s => s.name === c.name) || { agent: true, status: c.status }).label;
      case "disk": return diskOf(c) ?? -1;
      case "tokens": return tokensOf(c) ?? -1;
      case "up": return c.started ? now() - c.started : -1;
      default: return c[key] ?? -1;
    }
  },

  renderTable(cells) {
    const rows = [...cells].sort((a, b) => {
      const x = this.value(a, this.sort), y = this.value(b, this.sort);
      return (typeof x === "string" ? x.localeCompare(y) : x - y) * this.dir;
    });
    const head = COLUMNS.map(([key, label, num]) =>
      `<th class="${num ? "num" : ""}" data-k="${key}">${label}<span class="arr">${this.sort === key ? (this.dir < 0 ? "↓" : "↑") : ""}</span></th>`).join("");
    const body = rows.map(c => {
      const s = state.screens.find(x => x.name === c.name) || { agent: true, status: c.status };
      const st = agentState(s);
      const share = c.mem != null && c.mem_max ? c.mem / c.mem_max : null;
      const bar = share == null ? "" : `<span class="track"><i class="${share > .9 ? "max" : share > .7 ? "hot" : ""}" style="width:${Math.min(100, share * 100).toFixed(1)}%"></i></span>`;
      const d = diskOf(c);
      return `<tr data-name="${esc(c.name)}">
        <td><span class="who">${avatar(`cell ${c.name}`)}${esc(c.name)}<span class="chip-rt ${esc(c.runtime)}">${esc(runtimeLabel(c.runtime))}</span></span></td>
        <td><span class="status"><span class="dot ${st.dot}"></span>${esc(st.label)}</span></td>
        <td class="num">${pct(c.cpu)}</td>
        <td class="num" title="${c.mem_max ? `Limit ${bytes(c.mem_max)}` : "No limit"}${c.mem_peak ? ` · peak ${bytes(c.mem_peak)}` : ""}"><span class="membar">${bar}${bytes(c.mem)}</span></td>
        <td class="num" title="${c.disk ? `Home ${bytes(c.disk.home)} · logs and inbox ${bytes(c.disk.state)}` : "Measuring"}">${d == null ? `<span class="sub">measuring</span>` : bytes(d)}</td>
        <td class="num">${c.tokens ? `${count(c.tokens.input)} <span class="sub">in</span> ${count(c.tokens.output)} <span class="sub">out</span>` : "—"}</td>
        <td class="num">${c.pids ?? "—"}</td>
        <td class="num">${c.started ? dur(now() - c.started) : "—"}</td></tr>`;
    }).join("");
    $("mtable").innerHTML = rows.length ? `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`
      : `<div class="none">No agents running.</div>`;
    $("mtable").querySelectorAll("th").forEach(th => th.onclick = () => {
      const k = th.dataset.k;
      this.dir = this.sort === k ? -this.dir : (k === "name" || k === "status" ? 1 : -1);
      this.sort = k;
      store.set("cells.msort", k);
      store.set("cells.mdir", this.dir);
      this.renderTable(this.data.cells);
    });
    $("mtable").querySelectorAll("tbody tr").forEach(tr => tr.onclick = () => go(`#/agent/${encodeURIComponent(tr.dataset.name)}`));
  },
};

function paintTileUsage() {
  for (const [name, t] of tiles) {
    const c = Metrics.byName[name];
    const text = c && c.mem != null ? bytes(c.mem) : "";
    if (t.tr.textContent !== text) t.tr.textContent = text;
    t.tr.title = c ? `CPU ${pct(c.cpu)} · memory ${bytes(c.mem)} · ${c.pids ?? "—"} processes` : "";
  }
}
