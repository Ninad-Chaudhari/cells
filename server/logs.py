"""An agent's chat, read incrementally from its stream.jsonl and served in pages."""
import threading
from collections import OrderedDict

from .events import Converter
from .jsonl import Tail

FIRST_READ = 6_000_000
CACHED_STREAMS = 12
PAGE = 150


class _Feed:
    def __init__(self):
        self.tail = Tail(FIRST_READ)
        self.convert = Converter()
        self.out = []

    def add(self, ev):
        self.convert.add(ev, self.out)


_feeds = OrderedDict()
_lock = threading.Lock()


def _load(stream):
    """The stream's entries so far. Entries are only ever appended, so callers can ask for what's new by index."""
    key = str(stream)
    with _lock:
        feed = _feeds.get(key) or _Feed()
        restarted = feed.tail.read(stream, feed.add)
        if restarted is None:
            _feeds.pop(key, None)
            return []
        if restarted:
            feed = _Feed()
            feed.tail.read(stream, feed.add)
        _feeds[key] = feed
        _feeds.move_to_end(key)
        while len(_feeds) > CACHED_STREAMS:
            _feeds.popitem(last=False)
        return feed.out


def feed(stream, since=0):
    """(total, entries[since:])."""
    out = _load(stream)
    return len(out), out[since:]


def page(stream, before=None, limit=PAGE):
    """(start, total, entries[start:before]): one page ending at `before` (default: the end). A page never
    starts with a tool's output, so the output stays next to the call that made it."""
    out = _load(stream)
    end = len(out) if before is None else max(0, min(before, len(out)))
    start = max(0, end - limit)
    while start > 0 and out[start][0] in ("result", "error"):
        start -= 1
    return start, len(out), out[start:end]
