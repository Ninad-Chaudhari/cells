"""HTTP routes for the dashboard."""
import hashlib
import json
import mimetypes
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse

from . import agents, history, inbox, knowledge, logs, runtimes
from .cells import cell_dir, display_of, list_cells
from .config import FILE_RE, MAX, NAME, WEB
from .frames import FRAMES, LIVE_QUALITY, PREVIEW_QUALITY
from .metrics import METRICS
from .xinput import send_input

STATIC_RE = re.compile(r"^[a-z0-9_-]+\.(css|js|svg|png|ico)$")
INLINE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}
MAX_BODY = 64 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "cells"

    def address_string(self):
        return "local"

    def log_message(self, fmt, *args):
        pass

    # responses
    def send_bytes(self, code, body, ctype, cache="no-store", etag=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, code=200):
        self.send_bytes(code, json.dumps(obj).encode(), "application/json")

    def json_polled(self, obj):
        """JSON the browser polls: 304 when it hasn't changed since the caller's copy."""
        body = json.dumps(obj).encode()
        etag = '"' + hashlib.blake2b(body, digest_size=8).hexdigest() + '"'
        if self.headers.get("If-None-Match") == etag:
            return self.not_modified(etag)
        self.send_bytes(200, body, "application/json", "no-cache", etag)

    def not_modified(self, etag):
        self.send_response(304)
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def missing(self, what="not found"):
        self.json({"ok": False, "error": what}, 404)

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("request too large")
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw or b"{}")

    # GET
    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        parts = [unquote(p) for p in url.path.strip("/").split("/") if p]
        try:
            self.route_get(url.path, parts, q)
        except ValueError:
            self.json({"ok": False, "error": "bad request"}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def route_get(self, path, parts, q):
        arg = lambda k, d="": q.get(k, [d])[0]
        if path == "/":
            return self.send_bytes(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        if len(parts) == 2 and parts[0] == "static" and STATIC_RE.match(parts[1]) and (WEB / parts[1]).is_file():
            ctype = mimetypes.guess_type(parts[1])[0] or "application/octet-stream"
            return self.send_bytes(200, (WEB / parts[1]).read_bytes(), ctype, "no-cache")
        if path in ("/api/state", "/api/screens"):
            screens = json.dumps(list_cells())
            rts = json.dumps(runtimes.status())
            etag = '"' + hashlib.blake2b((screens + rts).encode(), digest_size=8).hexdigest() + '"'
            if self.headers.get("If-None-Match") == etag:
                return self.not_modified(etag)
            body = f'{{"now": {int(time.time())}, "host": {json.dumps(NAME)}, "max": {MAX}, "runtimes": {rts}, "screens": {screens}}}'
            return self.send_bytes(200, body.encode(), "application/json", "no-cache", etag)
        if len(parts) == 3 and parts[:2] == ["api", "log"]:
            d = cell_dir(parts[2])
            if not d:
                return self.missing()
            return self.json(self.log(d / "state" / "stream.jsonl", arg))
        if len(parts) == 2 and parts[0] in ("shot", "stream"):
            display = display_of(parts[1])
            if not display:
                return self.missing()
            width = int(arg("w", "0") or 0)
            if parts[0] == "shot":
                return self.shot(display, width)
            return self.stream(display, width, min(max(float(arg("fps", "5")), 0.5), 15.0))
        if len(parts) == 4 and parts[0] == "file":
            d = cell_dir(parts[1])
            rel = "/".join(parts[2:])
            p = d / "state" / "inbox" / rel if d and FILE_RE.match(rel) else None
            return self.image(p)
        if path == "/api/metrics":
            return self.json(METRICS.snapshot())
        if parts == ["api", "history"]:
            return self.json_polled({"runs": history.list_runs()})
        if len(parts) == 4 and parts[:2] == ["api", "history"] and parts[3] == "log":
            page = history.log_page(parts[2], int(arg("before", "0") or 0))
            return self.json(page) if page else self.missing()
        if len(parts) == 3 and parts[:2] == ["api", "history"]:
            d = history.detail(parts[2])
            return self.json(d) if d else self.missing()
        if len(parts) >= 5 and parts[:2] == ["api", "history"] and parts[3] == "home":
            path = history.home_file(parts[2], "/".join(parts[4:]))
            if not path:
                return self.missing()
            ctype = mimetypes.guess_type(path.name)[0]
            return self.send_bytes(200, path.read_bytes(), ctype if ctype in INLINE_TYPES else "text/plain; charset=utf-8")
        if len(parts) == 6 and parts[:2] == ["api", "history"] and parts[3] == "file":
            rel = "/".join(parts[4:])
            return self.image(history.file_path(parts[2], rel) if FILE_RE.match(rel) else None)
        if path == "/api/kb/tree":
            return self.json_polled(knowledge.tree())
        if path == "/api/kb/doc":
            d = knowledge.doc(arg("path"))
            return self.json(d) if d else self.missing()
        if path == "/api/kb/commits":
            return self.json_polled({"commits": knowledge.commits()})
        if path == "/api/kb/commit":
            c = knowledge.commit(arg("hash"))
            return self.json(c) if c else self.missing()
        if path == "/api/kb/search":
            return self.json({"results": knowledge.search(arg("q"))})
        self.missing()

    def log(self, stream, arg):
        """Live chat: no params = the latest page; before=K = the page before entry K; since=N = what's new."""
        if arg("before"):
            start, _, entries = logs.page(stream, int(arg("before")))
            return {"start": start, "entries": entries}
        since = arg("since")
        if since:
            since = int(since)
            total, new = logs.feed(stream, since)
            if since <= total and len(new) <= 500:
                return {"next": total, "entries": new}
        start, total, entries = logs.page(stream)
        return {"start": start, "next": total, "reset": bool(since), "entries": entries}

    def image(self, path):
        if not path or not path.is_file():
            return self.missing()
        self.send_bytes(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png", "private, max-age=86400")

    def shot(self, display, width):
        """One preview frame. Answers 304 when the screen hasn't changed since the caller's copy."""
        digest, jpg = FRAMES.jpeg(display, width, PREVIEW_QUALITY)
        etag = f'"{digest}.{width}"'
        if self.headers.get("If-None-Match") == etag:
            return self.not_modified(etag)
        self.send_bytes(200, jpg, "image/jpeg", "no-cache", etag)

    def stream(self, display, width, fps):
        """MJPEG for the screen being watched. Sends a frame when it changes, and every few seconds
        regardless so a closed viewer is noticed and its thread ends."""
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b"--frame\r\n")
        sent, last = None, 0.0
        while True:
            try:
                digest, jpg = FRAMES.jpeg(display, width, LIVE_QUALITY)
            except Exception:
                return
            t = time.monotonic()
            if digest != sent or t - last > 4:
                self.wfile.write(b"Content-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode()
                                 + b"\r\n\r\n" + jpg + b"\r\n--frame\r\n")
                self.wfile.flush()
                sent, last = digest, t
            time.sleep(1 / fps)

    # POST
    def do_POST(self):
        parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/") if p]
        try:
            body = self.body()
            self.route_post(parts, body)
        except (ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            self.json({"ok": False, "error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def route_post(self, parts, body):
        if parts == ["api", "agents"]:
            ok, msg = agents.start(body.get("name"), body.get("task"), body.get("images") or [], body.get("runtime"))
            return self.json({"ok": ok, "message": msg}, 200 if ok else 409)
        if parts == ["api", "history", "clear"]:
            return self.json({"ok": True, "deleted": history.clear()})
        if len(parts) == 4 and parts[:2] == ["api", "history"] and parts[3] == "delete":
            ok = history.delete(parts[2])
            return self.json({"ok": ok}, 200 if ok else 404)
        if len(parts) != 2:
            return self.missing()
        action, name = parts
        if not cell_dir(name):
            return self.missing("no such agent")
        if action == "input":
            send_input(display_of(name), body)
            return self.json({"ok": True})
        if action == "message":
            ok, err = inbox.queue_message(name, str(body.get("text", "")), body.get("images") or [])
            return self.json({"ok": ok, "error": err}, 200 if ok else 409)
        handlers = {
            "pause": lambda: agents.set_paused(name, True),
            "resume": lambda: agents.set_paused(name, False),
            "resolve": lambda: agents.resolve_help(name, str(body.get("note", ""))),
            "stop": lambda: agents.stop(name),
        }
        if action not in handlers:
            return self.missing()
        ok = handlers[action]()
        self.json({"ok": ok}, 200 if ok else 409)
