"""Cells and their screens: listing, screenshots and synthetic input."""
import hashlib
import io
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from PIL import Image, ImageGrab

from .config import KEYS_RE, NAME_RE, SCREENS, read

X11 = Path("/tmp/.X11-unix")
STOPPING = set()
_results = {}


def cell_dir(name):
    if not NAME_RE.match(name or ""):
        return None
    d = SCREENS / name
    return d if (d / "display").exists() else None


def display_of(name):
    d = cell_dir(name)
    return f":{read(d / 'display')}" if d else None


def last_result(stream):
    """The latest final answer in a stream.jsonl, cached by size and mtime."""
    try:
        st = stream.stat()
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    cached = _results.get(str(stream))
    if cached and cached[0] == key:
        return cached[1]
    result = None
    with open(stream, "rb") as fh:
        fh.seek(max(0, st.st_size - 400_000))
        lines = fh.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        if '"result"' not in line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            result = ev.get("result") or ev.get("subtype")
            break
    _results[str(stream)] = (key, result)
    return result


def pending_messages(state):
    out = []
    for p in sorted((state / "inbox").glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        out.append({"text": data.get("text", ""), "images": data.get("images", [])})
    return out


def list_screens():
    out = []
    for f in sorted(SCREENS.glob("*/display")):
        n = read(f)
        if not n or not (X11 / f"X{n}").exists():
            continue
        d = f.parent
        state = d / "state"
        help_req = None
        if (state / "help.json").exists():
            try:
                help_req = json.loads((state / "help.json").read_text())
            except ValueError:
                help_req = {"message": "(unreadable help request)", "at": None}
        started = read(state / "started") or read(d / "started")
        status = read(state / "status")
        done = bool(status) and status not in ("starting", "running")
        out.append({
            "name": d.name,
            "display": f":{n}",
            "started": int(started) if started else None,
            "agent": state.is_dir(),
            "status": status,
            "task": read(state / "task.txt"),
            "paused": (state / "paused").exists(),
            "help": help_req,
            "result": last_result(state / "stream.jsonl") if done else None,
            "pending": pending_messages(state),
            "stopping": d.name in STOPPING,
        })
    return out


PREVIEW_QUALITY = 68
LIVE_QUALITY = 82


class Frames:
    """Captures each screen at most once per tick, however many viewers ask, and skips unchanged frames."""

    def __init__(self, max_age=0.08):
        self.max_age = max_age
        self.lock = threading.Lock()
        self.locks = {}
        self.frames = {}
        self.jpegs = {}

    def frame(self, display):
        with self.lock:
            lock = self.locks.setdefault(display, threading.Lock())
        with lock:
            hit = self.frames.get(display)
            if hit and time.monotonic() - hit[0] < self.max_age:
                return hit
            im = ImageGrab.grab(xdisplay=display).convert("RGB")
            hit = (time.monotonic(), hashlib.blake2b(im.tobytes(), digest_size=8).hexdigest(), im)
            self.frames[display] = hit
            return hit

    def jpeg(self, display, width=0, quality=LIVE_QUALITY):
        """(frame digest, JPEG) of the current screen; width 0 means native, others round up to 160 px steps."""
        _, digest, im = self.frame(display)
        width = min(im.width, max(320, -(-width // 160) * 160)) if width > 0 else im.width
        key = (display, width, quality)
        cached = self.jpegs.get(key)
        if cached and cached[0] == digest:
            return cached
        if width < im.width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS, reducing_gap=2.0)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality)
        self.jpegs[key] = (digest, buf.getvalue())
        return self.jpegs[key]


FRAMES = Frames()


def xdotool(display, *args):
    return subprocess.run(["xdotool", *args], env={**os.environ, "DISPLAY": display},
                          capture_output=True, text=True, timeout=10)


def send_input(display, ev):
    kind = ev.get("type")
    if kind in ("click", "scroll"):
        w, h = (int(v) for v in xdotool(display, "getdisplaygeometry").stdout.split())
        x = round(min(max(float(ev["x"]), 0.0), 1.0) * (w - 1))
        y = round(min(max(float(ev["y"]), 0.0), 1.0) * (h - 1))
        button = str(int(ev.get("button", 1))) if kind == "click" else ("4" if float(ev.get("dy", 0)) < 0 else "5")
        xdotool(display, "mousemove", "--sync", str(x), str(y), "click", button)
    elif kind == "key":
        keys = str(ev.get("keys", ""))
        if KEYS_RE.match(keys):
            xdotool(display, "key", "--", keys)
    elif kind == "text":
        text = str(ev.get("text", ""))[:2000]
        if text:
            xdotool(display, "type", "--delay", "15", "--", text)
