"""Archived runs in $CELLS_HOME/history: list, inspect and delete."""
import shutil

from . import logs
from .config import ARCHIVE_RE, HISTORY, read
from .cells import last_result


def _dir(archive_id):
    if not ARCHIVE_RE.match(archive_id or ""):
        return None
    d = HISTORY / archive_id
    return d if d.is_dir() else None


def _meta(d):
    started, ended = read(d / "started"), read(d / "ended")
    return {
        "id": d.name,
        "name": d.name.split("-", 2)[2],
        "status": read(d / "status") or "stopped",
        "runtime": read(d / "runtime") or "claude",
        "task": read(d / "task.txt") or "",
        "started": int(started) if started and started.isdigit() else None,
        "ended": int(ended) if ended and ended.isdigit() else None,
        "result": read(d / "result.txt") or last_result(d / "stream.jsonl") or "",
    }


_metas = {}


def list_runs():
    """Newest first, without results (the detail has them). An archive is re-read only when its folder changes."""
    if not HISTORY.is_dir():
        return []
    runs, live = [], set()
    for d in HISTORY.iterdir():
        if not ARCHIVE_RE.match(d.name):
            continue
        try:
            mtime = d.stat().st_mtime_ns
        except OSError:
            continue
        live.add(d.name)
        hit = _metas.get(d.name)
        if not hit or hit[0] != mtime:
            hit = _metas[d.name] = (mtime, _meta(d))
        m = hit[1]
        runs.append({k: m[k] for k in ("id", "name", "status", "runtime", "started", "ended")} | {"task": m["task"][:300]})
    for gone in set(_metas) - live:
        _metas.pop(gone, None)
    return sorted(runs, key=lambda r: r["id"], reverse=True)


def detail(archive_id):
    d = _dir(archive_id)
    if not d:
        return None
    files = []
    home = d / "home"
    if home.is_dir():
        for p in sorted(home.rglob("*")):
            if p.is_file() and not any(part.startswith(".") for part in p.relative_to(home).parts):
                files.append({"path": p.relative_to(home).as_posix(), "size": p.stat().st_size})
    start, _, entries = logs.page(d / "stream.jsonl")
    return {**_meta(d), "files": files[:300], "start": start, "entries": entries}


def log_page(archive_id, before):
    d = _dir(archive_id)
    if not d:
        return None
    start, _, entries = logs.page(d / "stream.jsonl", before)
    return {"start": start, "entries": entries}


def file_path(archive_id, rel):
    d = _dir(archive_id)
    if not d:
        return None
    path = (d / "inbox" / rel).resolve()
    return path if (d / "inbox").resolve() in path.parents and path.is_file() else None


def home_file(archive_id, rel):
    """A file the agent left in its home, never a dotfile or anything outside it."""
    d = _dir(archive_id)
    if not d or not rel or any(part.startswith(".") for part in rel.split("/")):
        return None
    home = (d / "home").resolve()
    path = (home / rel).resolve()
    return path if home in path.parents and path.is_file() else None


def delete(archive_id):
    d = _dir(archive_id)
    if not d:
        return False
    shutil.rmtree(d)
    return True


def clear():
    n = 0
    for d in list(HISTORY.iterdir()) if HISTORY.is_dir() else []:
        if d.is_dir() and ARCHIVE_RE.match(d.name):
            shutil.rmtree(d)
            n += 1
    return n
