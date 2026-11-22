"""Turns an agent's stream.jsonl into a compact activity feed, reading only what was appended since last time."""
import json
import os
import threading
from collections import OrderedDict

SUMMARY_KEYS = ("url", "command", "query", "pattern", "file_path", "path", "folder_path",
                "element", "text", "name", "function")
FIRST_READ = 6_000_000
CACHED_STREAMS = 32
PAGE = 150


def short(value, limit, keep_lines=False):
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    s = s.strip() if keep_lines else " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _summary(inp):
    if not isinstance(inp, dict):
        return ""
    for k in SUMMARY_KEYS:
        if isinstance(inp.get(k), str) and inp[k].strip():
            return inp[k]
    return next((v for v in inp.values() if isinstance(v, str)), "")


def _convert(ev, out):
    kind = ev.get("type")
    if kind in ("assistant", "user"):
        for block in ev.get("message", {}).get("content", []) or []:
            if not isinstance(block, dict):
                continue
            t = block.get("type")
            if t == "text" and block.get("text", "").strip():
                out.append(["say", short(block["text"], 6000, True)])
            elif t == "tool_use":
                inp = block.get("input") or {}
                tool = block.get("name", "").replace("mcp__playwright__", "")
                out.append(["tool", tool, {"summary": short(_summary(inp), 240), "args": short(inp, 2000, True)}])
            elif t == "tool_result":
                content = block.get("content")
                if isinstance(content, list):
                    content = "\n".join(c.get("text", "[image]") for c in content if isinstance(c, dict))
                out.append(["error" if block.get("is_error") else "result", short(content or "", 3000, True)])
    elif kind == "result":
        result = ev.get("result") or ""
        echo = bool(out) and out[-1][0] == "say" and out[-1][1] == short(result, 6000, True)
        out.append(["done", short(result or ev.get("subtype", ""), 8000, True), {"echo": echo}])
    elif kind == "cell_message":
        out.append(["you", short(ev.get("text", ""), 8000, True),
                    {"via": ev.get("via", ""), "images": ev.get("images", []), "at": ev.get("at")}])


class _Stream:
    def __init__(self):
        self.ino, self.pos, self.tail, self.out = None, 0, b"", []


_streams = OrderedDict()
_lock = threading.Lock()


def feed(stream, since=0):
    """(total, entries[since:]). Entries are [kind, text] or [kind, text, extra] and are only ever
    appended, so a caller that has seen `total` entries asks with since=total next time.

    kinds: say (agent text), tool, result, error, done (final answer; echo=True when it repeats the
    last say), you (operator message).
    """
    out = _load(stream)
    return len(out), out[since:]


def page(stream, before=None, limit=PAGE):
    """(start, total, entries[start:before]): one page of history ending at `before` (default: the end).
    A page never starts with a tool's output, so the output stays next to the call that made it."""
    out = _load(stream)
    end = len(out) if before is None else max(0, min(before, len(out)))
    start = max(0, end - limit)
    while start > 0 and out[start][0] in ("result", "error"):
        start -= 1
    return start, len(out), out[start:end]


def _load(stream):
    key = str(stream)
    with _lock:
        try:
            fh = open(stream, "rb")
        except OSError:
            _streams.pop(key, None)
            return []
        with fh:
            st = os.fstat(fh.fileno())
            s = _streams.get(key)
            if s is None or s.ino != st.st_ino or st.st_size < s.pos:
                s = _Stream()
                s.ino = st.st_ino
                s.pos = max(0, st.st_size - FIRST_READ)
                skip_partial = s.pos > 0
            else:
                skip_partial = False
            _streams[key] = s
            _streams.move_to_end(key)
            while len(_streams) > CACHED_STREAMS:
                _streams.popitem(last=False)
            if st.st_size > s.pos:
                fh.seek(s.pos)
                chunk = fh.read(st.st_size - s.pos)
                s.pos += len(chunk)
                lines = (s.tail + chunk).split(b"\n")
                s.tail = lines.pop()
                if skip_partial and lines:
                    lines.pop(0)
                for line in lines:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(ev, dict):
                        _convert(ev, s.out)
        return s.out
