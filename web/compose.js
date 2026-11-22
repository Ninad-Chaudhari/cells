/* Shared by the chat and the launcher: image attachments (pick, paste, drop) and a growing textarea. */
const MAX_IMAGES = 6, MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];

function autosize(el, max = 200) {
  el.style.height = "";
  el.style.height = Math.min(el.scrollHeight, max) + "px";
}

class Attachments {
  constructor({ list, pick, input, drop, dropzone, paste, enabled = () => true }) {
    this.files = [];
    this.list = list;
    this.enabled = enabled;
    pick.onclick = e => { e.preventDefault(); input.click(); };
    input.onchange = () => { this.add(input.files); input.value = ""; };
    paste.addEventListener("paste", e => {
      const imgs = [...(e.clipboardData?.files || [])].filter(f => f.type.startsWith("image/"));
      if (imgs.length) { e.preventDefault(); this.add(imgs); }
    });
    let depth = 0;
    const show = on => dropzone.classList.toggle("hidden", !on);
    drop.addEventListener("dragenter", e => { if ([...e.dataTransfer.types].includes("Files") && this.enabled()) { depth++; show(true); } });
    drop.addEventListener("dragleave", () => { depth = Math.max(0, depth - 1); if (!depth) show(false); });
    drop.addEventListener("dragover", e => { if (this.enabled()) e.preventDefault(); });
    drop.addEventListener("drop", e => { e.preventDefault(); depth = 0; show(false); if (this.enabled()) this.add(e.dataTransfer.files); });
  }

  add(fileList) {
    for (const f of fileList) {
      if (!IMAGE_TYPES.includes(f.type)) { toast("Only PNG, JPEG, GIF or WebP images", "x"); continue; }
      if (f.size > MAX_IMAGE_BYTES) { toast(`${f.name || "Image"} is over 8 MB`, "x"); continue; }
      if (this.files.length >= MAX_IMAGES) { toast(`Up to ${MAX_IMAGES} images per message`, "x"); break; }
      this.files.push({ file: f, url: URL.createObjectURL(f) });
    }
    this.render();
  }

  remove(i) {
    URL.revokeObjectURL(this.files[i].url);
    this.files.splice(i, 1);
    this.render();
  }

  clear() {
    for (const f of this.files) URL.revokeObjectURL(f.url);
    this.files = [];
    this.render();
  }

  render() {
    this.list.innerHTML = this.files.map((f, i) => `<div class="att"><img src="${f.url}" alt=""><button type="button" data-i="${i}" aria-label="Remove">${icon("x")}</button></div>`).join("");
    this.list.querySelectorAll("button").forEach(b => b.onclick = () => this.remove(Number(b.dataset.i)));
  }

  /* [{type, name, data(base64)}] for the API. */
  encode() {
    return Promise.all(this.files.map(({ file }) => new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve({ type: file.type, name: file.name || "image", data: String(r.result).split(",", 2)[1] });
      r.onerror = reject;
      r.readAsDataURL(file);
    })));
  }
}
