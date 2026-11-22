/* Shared helpers: icons, markdown, time, avatars, toasts, API. */
const ICONS = {
  grid: '<rect x="3.5" y="4" width="7.5" height="7" rx="1.6"/><rect x="13" y="4" width="7.5" height="7" rx="1.6"/><rect x="3.5" y="13" width="7.5" height="7" rx="1.6"/><rect x="13" y="13" width="7.5" height="7" rx="1.6"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  alert: '<path d="M12 3.5 2.8 19.5h18.4L12 3.5z"/><path d="M12 10v4"/><path d="M12 17h.01"/>',
  back: '<path d="M14.5 18 8.5 12l6-6"/>',
  pause: '<rect x="6.5" y="5" width="3.5" height="14" rx="1"/><rect x="14" y="5" width="3.5" height="14" rx="1"/>',
  play: '<path d="M7.5 5v14l11-7-11-7z"/>',
  stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="2.5"/>',
  hand: '<path d="M8 13V5.8a1.5 1.5 0 0 1 3 0V12"/><path d="M11 11V4.8a1.5 1.5 0 0 1 3 0V11"/><path d="M14 11V6.8a1.5 1.5 0 0 1 3 0V13"/><path d="M17 9.8a1.5 1.5 0 0 1 3 0V15a6 6 0 0 1-6 6h-1.2a6 6 0 0 1-4.5-2l-3.6-4.2a1.6 1.6 0 0 1 2.4-2.1L8 14.6"/>',
  release: '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
  x: '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  up: '<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  enter: '<path d="M20 5v7a3 3 0 0 1-3 3H5"/><path d="M9 11l-4 4 4 4"/>',
  keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M7.5 14h9"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  clip: '<path d="M20.5 11.5 12 20a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l7.9-7.9"/>',
  trash: '<path d="M4.5 6.5h15M9.5 6.5V4.5h5v2M6.5 6.5l1 13h9l1-13"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.5 2.6 2.5 14.4 0 17M12 3.5c-2.5 2.6-2.5 14.4 0 17"/>',
  cursor: '<path d="M5 3.5l13 7-5.5 1.8L10.7 18 5 3.5z"/>',
  terminal: '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M7 9.5l3 2.5-3 2.5"/><path d="M12.5 15h4.5"/>',
  file: '<path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10z"/><path d="M14 3.5v5h5"/>',
  eye: '<path d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.5"/>',
  bolt: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>',
  hourglass: '<path d="M6.5 3.5h11M6.5 20.5h11"/><path d="M7.5 3.5c0 5 9 6 9 8.5s-9 3.5-9 8.5"/><path d="M16.5 3.5c0 5-9 6-9 8.5s9 3.5 9 8.5"/>',
  reply: '<path d="M9.5 8 4.5 12.5l5 4.5"/><path d="M4.5 12.5h9a6 6 0 0 1 6 6v.5"/>',
  sparkle: '<path d="M12 3.5l1.8 5.2 5.2 1.8-5.2 1.8L12 17.5l-1.8-5.2-5.2-1.8 5.2-1.8z"/>',
  monitor: '<rect x="3" y="4.5" width="18" height="12" rx="2.2"/><path d="M9 20h6M12 16.5V20"/>',
  split: '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><path d="M14 4.5v15"/>',
  chat: '<path d="M5 18.5V7a2.5 2.5 0 0 1 2.5-2.5h9A2.5 2.5 0 0 1 19 7v6.5a2.5 2.5 0 0 1-2.5 2.5H8.5z"/>',
  chev: '<path d="M9.5 6l6 6-6 6"/>',
};
const icon = n => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function hydrate(root) {
  root.querySelectorAll("[data-icon]").forEach(el => {
    if (!el.dataset.h) { el.insertAdjacentHTML("afterbegin", icon(el.dataset.icon)); el.dataset.h = 1; }
  });
}

if (window.DOMPurify) DOMPurify.addHook("afterSanitizeAttributes", n => {
  if (n.tagName === "A") { n.setAttribute("target", "_blank"); n.setAttribute("rel", "noopener noreferrer"); }
});
function md(text) {
  const s = String(text ?? "");
  if (window.marked && window.DOMPurify) return DOMPurify.sanitize(marked.parse(s, { gfm: true, breaks: true }));
  return esc(s).replace(/\n/g, "<br>");
}
function plain(text) {
  return String(text ?? "").replace(/```[\s\S]*?```/g, " ").replace(/`([^`]+)`/g, "$1").replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+/gm, "").replace(/(\*\*|__|\*|_)(.+?)\1/g, "$2").replace(/\|/g, " ").replace(/\s+/g, " ").trim();
}
const tidyPath = s => String(s || "").replace(/^\/(home\/(users\/)?[^/]+|Users\/[^/]+|root)\/(\.cell\/)?/, "~/");

const clock = { offset: 0 };
const now = () => Date.now() / 1000 + clock.offset;
function dur(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${String(s).padStart(2, "0")}s` : `${s}s`;
}
function ago(t) {
  const s = Math.max(0, now() - t);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
const bytes = n => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;

const PALETTE = ["#8aa8ff", "#a78bfa", "#34d399", "#fbbf24", "#f472b6", "#60a5fa", "#fb923c", "#2dd4bf"];
function who(author) {
  const a = String(author || "");
  if (a.startsWith("cell ")) return { name: a.slice(5), kind: "agent" };
  if (a === "cells") return { name: "setup", kind: "system" };
  return { name: a, kind: "person" };
}
function avatar(author, sm) {
  const w = who(author);
  const parts = w.name.split(/[-_\s]+/).filter(Boolean);
  const init = (parts.length > 1 ? parts[0][0] + parts[1][0] : w.name.slice(0, 2)).toUpperCase();
  let h = 0;
  for (const c of w.name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return `<span class="av${sm ? " sm" : ""}" style="background:${PALETTE[h % PALETTE.length]}" title="${esc(author)}">${esc(init)}</span>`;
}

function toast(text, ic = "check") {
  const t = document.createElement("div");
  t.className = "toast glass";
  t.innerHTML = icon(ic) + `<span>${esc(text)}</span>`;
  $("toasts").appendChild(t);
  setTimeout(() => t.remove(), 2800);
}

const api = {
  etags: {},
  async get(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },
  /* GET that returns null when the server says nothing changed since the last answer. */
  async poll(path) {
    const tag = this.etags[path];
    const r = await fetch(path, { cache: "no-store", headers: tag ? { "If-None-Match": tag } : {} });
    if (r.status === 304) return null;
    if (!r.ok) throw new Error(`${r.status}`);
    this.etags[path] = r.headers.get("ETag") || "";
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, { method: "POST", body: JSON.stringify(body || {}) });
    let data = {};
    try { data = await r.json(); } catch (e) {}
    return { ok: r.ok && data.ok !== false, ...data };
  },
};

/* localStorage that never throws (private windows, blocked storage). */
const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, String(v)); } catch (e) {} },
};

/* Two-click confirm for destructive buttons. */
function armThenRun(btn, run, labelEl, labels) {
  if (btn.classList.contains("armed")) {
    clearTimeout(btn._t);
    btn.classList.remove("armed");
    if (labelEl) labelEl.textContent = labels[0];
    run();
    return;
  }
  btn.classList.add("armed");
  if (labelEl) labelEl.textContent = labels[1];
  btn._t = setTimeout(() => { btn.classList.remove("armed"); if (labelEl) labelEl.textContent = labels[0]; }, 3000);
}
