"""Controlling agents: start, stop, pause, resume, answer help, and queue messages."""
import base64
import binascii
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from .config import CELL, IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES, NAME_RE, UNIT, read
from .screens import STOPPING, cell_dir


def start(name, task, images=()):
    """Start an agent on a task. Images go to its inbox, so it reads them as soon as it starts working."""
    name, task = (name or "").strip(), (task or "").strip()
    if not NAME_RE.match(name):
        return False, "Name: lowercase letters, digits and dashes, up to 31 characters."
    if not task:
        return False, "Give the agent a task."
    _, err = decode_images(images)
    if err:
        return False, err
    r = subprocess.run([str(CELL), "up", name, task[:20000]], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    if images:
        queue_message(name, "Images for your task.", images)
    return True, r.stdout.strip()


def stop(name):
    if name in STOPPING:
        return True

    def run():
        try:
            subprocess.run([str(CELL), "down", name], capture_output=True, timeout=180)
        finally:
            STOPPING.discard(name)

    STOPPING.add(name)
    threading.Thread(target=run, daemon=True).start()
    return True


def _claude_pids(name):
    cg = subprocess.run(["systemctl", "--user", "show", "-p", "ControlGroup", "--value", f"{UNIT}-agent-{name}"],
                        capture_output=True, text=True, timeout=10).stdout.strip()
    if not cg:
        return []
    return [int(p) for p in read(Path("/sys/fs/cgroup" + cg) / "cgroup.procs", "").split()
            if read(Path(f"/proc/{p}/comm")) == "claude"]


def set_paused(name, paused):
    d = cell_dir(name)
    pids = _claude_pids(name)
    if not d or not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGSTOP if paused else signal.SIGCONT)
        except ProcessLookupError:
            pass
    flag = d / "state" / "paused"
    if paused:
        flag.touch()
    else:
        flag.unlink(missing_ok=True)
    return True


def resolve_help(name, note):
    d = cell_dir(name)
    if not d:
        return False
    state = d / "state"
    (state / "help-answer").write_text(note.strip() or "done")
    (state / "help.json").unlink(missing_ok=True)
    if (state / "paused").exists():
        set_paused(name, False)
    return True


def decode_images(images):
    """([(ext, bytes)], error) for images sent as {type, data(base64)}."""
    images = list(images or [])
    if len(images) > MAX_IMAGES:
        return [], f"Up to {MAX_IMAGES} images per message."
    decoded = []
    for img in images:
        ext = IMAGE_TYPES.get(str(img.get("type", "")))
        if not ext:
            return [], "Images must be PNG, JPEG, GIF or WebP."
        try:
            data = base64.b64decode(str(img.get("data", "")), validate=True)
        except (binascii.Error, ValueError):
            return [], "An image could not be read."
        if len(data) > MAX_IMAGE_BYTES:
            return [], "Each image must be under 8 MB."
        decoded.append((ext, data))
    return decoded, ""


def queue_message(name, text, images=()):
    """Write a message (and its images) to the agent's inbox atomically. Nothing is written if any image is bad."""
    d = cell_dir(name)
    text = (text or "").strip()[:8000]
    if not d or read(d / "state" / "status") not in ("starting", "running", "idle"):
        return False, "This agent has ended."
    decoded, err = decode_images(images)
    if err:
        return False, err
    if not (text or decoded):
        return False, "Write a message or attach an image."
    inbox = d / "state" / "inbox"
    (inbox / "files").mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    saved = []
    for i, (ext, data) in enumerate(decoded):
        rel = f"files/{stamp}-{i}.{ext}"
        (inbox / rel).write_bytes(data)
        saved.append(rel)
    tmp = inbox / f".{stamp}.tmp"
    tmp.write_text(json.dumps({"text": text, "images": saved, "at": int(time.time())}))
    os.rename(tmp, inbox / f"{stamp}.json")
    return True, ""
