"""The cells on this host and what each is doing, read from $CELLS_HOME/screens."""
import json
import threading
from collections import OrderedDict
from pathlib import Path

from .config import NAME_RE, SCREENS, read

X11 = Path("/tmp/.X11-unix")
STOPPING = set()

_results = OrderedDict()
_results_lock = threading.Lock()
RESULTS_CACHED = 64


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
    with _results_lock:
        hit = _results.get(str(stream))
        if hit and hit[0] == key:
            return hit[1]
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
    with _results_lock:
        _results[str(stream)] = (key, result)
        _results.move_to_end(str(stream))
        while len(_results) > RESULTS_CACHED:
            _results.popitem(last=False)
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


def list_cells():
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
            "runtime": read(state / "runtime") or "claude",
            "status": status,
            "task": read(state / "task.txt"),
            "paused": (state / "paused").exists(),
            "help": help_req,
            "result": last_result(state / "stream.jsonl") if done else None,
            "pending": pending_messages(state),
            "stopping": d.name in STOPPING,
        })
    return out
