/* The chat composer on an agent's page: text plus images, queued-message preview, delivery hint. */
const Chat = {
  enabled: true, att: null, delivKey: "",

  reset() {
    this.att.clear();
    $("msg").value = "";
    autosize($("msg"));
    $("queued").dataset.k = "";
    $("queued").innerHTML = "";
  },

  setEnabled(on, placeholder) {
    this.enabled = on;
    for (const id of ["msg", "msgSend", "attach"]) $(id).disabled = !on;
    $("msg").placeholder = placeholder;
  },

  update(s) {
    const can = chattable(s);
    this.setEnabled(can, !s.agent ? "Plain screen" : !can ? "This agent has ended" : s.status === "idle" ? `Reply to ${s.name}` : `Message ${s.name}`);
    const mode = !can ? "" : s.status === "idle" ? "idle" : "busy";
    if (mode !== this.delivKey) {
      this.delivKey = mode;
      $("deliv").innerHTML = mode === "idle" ? `${icon("reply")}<span data-tip="It finished and is waiting. Your message starts a new turn." data-tip-pos="up">New turn</span>`
        : mode === "busy" ? `${icon("hourglass")}<span data-tip="It's working. Your message reaches it after its current step." data-tip-pos="up">Next step</span>` : "";
    }
    const pending = s.pending || [];
    const key = JSON.stringify(pending);
    if ($("queued").dataset.k !== key) {
      $("queued").dataset.k = key;
      $("queued").innerHTML = pending.map(m => `<div class="q">${esc(m.text || "")}${m.images?.length ? ` · ${m.images.length} image${m.images.length > 1 ? "s" : ""}` : ""}</div>`).join("");
    }
  },

  async send() {
    const text = $("msg").value.trim();
    if (!this.enabled || (!text && !this.att.files.length)) return;
    $("msgSend").disabled = true;
    try {
      const images = await this.att.encode();
      const r = await Focus.post("message", { text, images });
      if (!r.ok) { toast(r.error || "Couldn't send", "x"); return; }
      const idle = Focus.current.status === "idle";
      this.reset();
      toast(idle ? "Sent" : "Queued for its next step", idle ? "check" : "hourglass");
      refreshScreens();
    } finally {
      $("msgSend").disabled = !this.enabled;
    }
  },

  bind() {
    this.att = new Attachments({ list: $("attachments"), pick: $("attach"), input: $("filePick"), drop: $("side"),
      dropzone: $("dropzone"), paste: $("msg"), enabled: () => this.enabled });
    $("msgSend").onclick = () => this.send();
    $("msg").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); this.send(); } });
    $("msg").addEventListener("input", () => autosize($("msg")));
  },
};
