"""Screen capture. Each screen is captured at most once per tick however many viewers ask, each size is
encoded once per frame, and anything nobody has asked for in a while is dropped."""
import hashlib
import io
import threading
import time

from PIL import Image, ImageGrab

PREVIEW_QUALITY = 68
LIVE_QUALITY = 82
FORGET_AFTER = 30


class Frames:
    def __init__(self, max_age=0.08):
        self.max_age = max_age
        self.lock = threading.Lock()
        self.locks = {}
        self.frames = {}
        self.jpegs = {}
        self.pruned = time.monotonic()

    def frame(self, display):
        with self.lock:
            lock = self.locks.setdefault(display, threading.Lock())
        with lock:
            hit = self.frames.get(display)
            if hit and time.monotonic() - hit[0] < self.max_age:
                return hit
            im = ImageGrab.grab(xdisplay=display).convert("RGB")
            hit = (time.monotonic(), hashlib.blake2b(im.tobytes(), digest_size=8).hexdigest(), im)
            self.frames[display] = hit
            return hit

    def jpeg(self, display, width=0, quality=LIVE_QUALITY):
        """(frame digest, JPEG) of the current screen; width 0 means native, others round up to 160 px steps."""
        self.prune()
        _, digest, im = self.frame(display)
        width = min(im.width, max(320, -(-width // 160) * 160)) if width > 0 else im.width
        key = (display, width, quality)
        cached = self.jpegs.get(key)
        if cached and cached[0] == digest:
            self.jpegs[key] = (*cached[:2], time.monotonic())
            return cached[:2]
        if width < im.width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS, reducing_gap=2.0)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality)
        self.jpegs[key] = (digest, buf.getvalue(), time.monotonic())
        return digest, self.jpegs[key][1]

    def prune(self):
        """Drop captures and encodings nobody asked for in FORGET_AFTER seconds (a stopped cell, a closed tab)."""
        t = time.monotonic()
        if t - self.pruned < 5:
            return
        self.pruned = t
        with self.lock:
            for display, hit in list(self.frames.items()):
                if t - hit[0] > FORGET_AFTER:
                    self.frames.pop(display, None)
                    self.locks.pop(display, None)
            for key, hit in list(self.jpegs.items()):
                if t - hit[2] > FORGET_AFTER:
                    self.jpegs.pop(key, None)


FRAMES = Frames()
