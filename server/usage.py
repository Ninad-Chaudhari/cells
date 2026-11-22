"""Tokens each agent has used, from the runtimes' own end-of-turn reports: Claude Code's `result` event and
Codex's `turn.completed` each carry that turn's usage, so a session's total is their sum. (Claude's
per-message events carry usage from the start of streaming, which undercounts output, so they are not used.)"""
import threading
from collections import OrderedDict

from .jsonl import Tail

CACHED_STREAMS = 64


class _Usage:
    def __init__(self):
        self.tail = Tail()
        self.total = [0, 0, 0, 0]

    def add(self, ev):
        kind, u = ev.get("type"), ev.get("usage")
        if not isinstance(u, dict):
            return
        if kind == "result":
            cached = u.get("cache_read_input_tokens") or 0
            turn = ((u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + cached,
                    u.get("output_tokens") or 0, cached, (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0)
        elif kind == "turn.completed":
            turn = tuple(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens"))
        else:
            return
        self.total = [t + x for t, x in zip(self.total, turn)]

    def totals(self):
        return dict(zip(("input", "output", "cached", "reasoning"), self.total))


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
