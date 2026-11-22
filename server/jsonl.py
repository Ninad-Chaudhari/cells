"""Reads what was appended to a JSON-lines file since the last read: whole lines only, in bounded chunks,
starting over when the file is replaced or truncated."""
import json
import os

CHUNK = 4 * 1024 * 1024


class Tail:
    def __init__(self, first_read=None):
        self.first_read = first_read
        self.ino = None
        self.pos = 0
        self.partial = b""

    def read(self, path, handle):
        """Call handle(event) for each new JSON object. Returns True when the file was replaced since the
        last read (the caller should forget what it built from the old file), None when it is missing."""
        try:
            fh = open(path, "rb")
        except OSError:
            return None
        with fh:
            st = os.fstat(fh.fileno())
            restarted = self.ino is not None and (st.st_ino != self.ino or st.st_size < self.pos)
            skip = False
            if self.ino is None or restarted:
                self.ino, self.partial = st.st_ino, b""
                self.pos = max(0, st.st_size - self.first_read) if self.first_read else 0
                skip = self.pos > 0
            fh.seek(self.pos)
            while self.pos < st.st_size:
                chunk = fh.read(min(CHUNK, st.st_size - self.pos))
                if not chunk:
                    break
                self.pos += len(chunk)
                lines = (self.partial + chunk).split(b"\n")
                self.partial = lines.pop()
                if skip and lines:
                    lines.pop(0)
                    skip = False
                for line in lines:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(ev, dict):
                        handle(ev)
        return restarted
