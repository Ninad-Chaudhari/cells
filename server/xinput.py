"""Clicks, scrolls and keys on a cell's screen, for when you take over."""
import os
import subprocess

from .config import KEYS_RE


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
