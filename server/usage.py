"""Tokens each agent has used, from the runtimes' own reports. Claude Code repeats a message's usage on
every content block of that message, so each message id counts once (its latest report wins); Codex
reports usage once per turn."""
import threading
from collections import OrderedDict

from .jsonl import Tail

CACHED_STREAMS = 64


class _Usage:
    def __init__(self):
        self.tail = Tail()
        self.claude = {}
        self.codex = [0, 0, 0, 0]

    def add(self, ev):
        kind = ev.get("type")
        if kind == "assistant":
            msg = ev.get("message") or {}
            u = msg.get("usage") or {}
            if msg.get("id") and u:
                cached = u.get("cache_read_input_tokens") or 0
                inp = (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + cached
                self.claude[msg["id"]] = (inp, u.get("output_tokens") or 0, cached, 0)
        elif kind == "turn.completed":
            u = ev.get("usage") or {}
            for i, k in enumerate(("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens")):
                self.codex[i] += u.get(k) or 0

    def totals(self):
        t = [sum(v[i] for v in self.claude.values()) + self.codex[i] for i in range(4)]
        return {"input": t[0], "output": t[1], "cached": t[2], "reasoning": t[3]}


_cache = OrderedDict()
_lock = threading.Lock()


def totals(stream):
    key = str(stream)
    with _lock:
        u = _cache.get(key) or _Usage()
        restarted = u.tail.read(stream, u.add)
        if restarted is None:
            _cache.pop(key, None)
            return None
        if restarted:
            u = _Usage()
            u.tail.read(stream, u.add)
        _cache[key] = u
        _cache.move_to_end(key)
        while len(_cache) > CACHED_STREAMS:
            _cache.popitem(last=False)
        return u.totals()
