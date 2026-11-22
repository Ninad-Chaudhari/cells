"""Read-only views of the shared knowledge base: a git repo of Markdown docs."""
import os
import sqlite3
import subprocess

from .config import CONTEXTS, HASH_RE, KNOWLEDGE, KNOWLEDGE_GIT

LOG_FMT = "--format=\x01%h\x02%an\x02%at\x02%s"
GIT = ["git", "--no-optional-locks", f"--git-dir={KNOWLEDGE_GIT}", f"--work-tree={KNOWLEDGE}"]


def git(*args, limit=400_000):
    try:
        r = subprocess.run([*GIT, *args], capture_output=True, text=True, timeout=15,
                           env={**os.environ, "GIT_INDEX_FILE": f"{KNOWLEDGE}.index"})
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout[:limit]


def _descriptions():
    """Folder and doc descriptions, when OpenContext keeps its index next to the docs."""
    out = {"folders": {}, "docs": {}}
    db = KNOWLEDGE / "opencontext.db"
    if not db.exists():
        return out
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        out["folders"] = dict(con.execute("select rel_path, description from folders"))
        out["docs"] = dict(con.execute("select rel_path, description from docs"))
        con.close()
    except sqlite3.Error:
        pass
    return out


def _parse_log(text):
    commits, cur = [], None
    for line in text.splitlines():
        if line.startswith("\x01"):
            h, author, at, subject = line[1:].split("\x02", 3)
            cur = {"hash": h, "author": author, "at": int(at), "subject": subject, "files": []}
            commits.append(cur)
        elif line.strip() and cur is not None:
            parts = line.split("\t")
            if len(parts) == 3:
                adds, dels, path = parts
                cur["files"].append({"path": path, "adds": None if adds == "-" else int(adds),
                                     "dels": None if dels == "-" else int(dels)})
    return commits


def _title(text, fallback):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _doc_path(rel):
    path = (CONTEXTS / rel).resolve()
    if CONTEXTS.resolve() not in path.parents or path.suffix != ".md" or not path.is_file():
        return None
    return path


_cache = {}


def _cached(name, key, build):
    hit = _cache.get(name)
    if hit and hit[0] == key:
        return hit[1]
    value = build()
    _cache[name] = (key, value)
    return value


def _head():
    return git("rev-parse", "-q", "--verify", "HEAD").strip()


def _docs_stamp():
    """Changes when any doc or folder is added, removed or edited, or the search index is rewritten."""
    out = []
    for p in [KNOWLEDGE / "opencontext.db", *(CONTEXTS.rglob("*") if CONTEXTS.is_dir() else [])]:
        try:
            st = p.stat()
        except OSError:
            continue
        out.append((str(p), st.st_mtime_ns, st.st_size))
    return hash(tuple(out))


def tree():
    return _cached("tree", (_head(), _docs_stamp()), _tree)


def _tree():
    desc = _descriptions()
    last = {}
    for c in _parse_log(git("log", LOG_FMT, "--numstat", "--", "contexts")):
        for f in c["files"]:
            last.setdefault(f["path"], {k: c[k] for k in ("hash", "author", "at", "subject")})
    dirty = {line[3:].strip().strip('"') for line in git("status", "--porcelain", "--", "contexts").splitlines()}
    folders, docs = [], []
    if CONTEXTS.is_dir():
        for d in sorted(p for p in CONTEXTS.rglob("*") if p.is_dir()):
            rel = d.relative_to(CONTEXTS).as_posix()
            folders.append({"path": rel, "description": desc["folders"].get(rel)})
        for f in sorted(CONTEXTS.rglob("*.md")):
            rel = f.relative_to(CONTEXTS).as_posix()
            try:
                text, st = f.read_text(errors="replace"), f.stat()
            except OSError:
                continue
            key = f"contexts/{rel}"
            docs.append({
                "path": rel,
                "folder": f.parent.relative_to(CONTEXTS).as_posix() if f.parent != CONTEXTS else "",
                "title": _title(text, f.stem),
                "description": desc["docs"].get(rel),
                "mtime": int(st.st_mtime),
                "last": last.get(key),
                "dirty": any(x == key or key.startswith(x.rstrip("/") + "/") for x in dirty),
            })
    count = git("rev-list", "--count", "HEAD").strip()
    return {"folders": folders, "docs": docs, "commits": int(count) if count.isdigit() else 0}


def doc(rel):
    path = _doc_path(rel)
    if not path:
        return None
    text = path.read_text(errors="replace")[:300_000]
    return {
        "path": rel,
        "title": _title(text, path.stem),
        "description": _descriptions()["docs"].get(rel),
        "content": text,
        "mtime": int(path.stat().st_mtime),
        "history": _parse_log(git("log", LOG_FMT, "--numstat", "--follow", "--", f"contexts/{rel}")),
    }


def commits(limit=200):
    return _cached(f"commits{limit}", _head(), lambda: _parse_log(git("log", LOG_FMT, "--numstat", f"-{limit}")))


def commit(h):
    if not HASH_RE.match(h or ""):
        return None
    meta = _parse_log(git("show", LOG_FMT, "--numstat", h))
    if not meta:
        return None
    return {**meta[0], "body": git("show", "-s", "--format=%b", h).strip(),
            "diff": git("show", "--format=", "--no-color", "--patch", h, "--", "contexts", ".gitignore", limit=300_000)}


def search(q):
    q = (q or "").strip().lower()
    out = []
    if not q or not CONTEXTS.is_dir():
        return out
    for f in sorted(CONTEXTS.rglob("*.md")):
        try:
            lines = f.read_text(errors="replace").splitlines()
        except OSError:
            continue
        hits = [ln.strip()[:240] for ln in lines if q in ln.lower()][:3]
        rel = f.relative_to(CONTEXTS).as_posix()
        if hits or q in rel.lower():
            out.append({"path": rel, "title": _title("\n".join(lines), f.stem), "hits": hits})
    return out[:50]
