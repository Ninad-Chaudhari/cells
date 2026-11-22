"""A cell's inbox. Each message is a JSON file ({text, images, at}); its images sit in inbox/files.
A message is claimed by renaming it into inbox/delivered, so it is handed over exactly once, either by the
supervisor (a new turn) or by the in-sandbox hook (mid-task)."""
import json
import os
from typing import NamedTuple


class Message(NamedTuple):
    id: str
    text: str
    images: list


class Inbox:
    def __init__(self, path):
        self.path = path
        self.delivered = path / "delivered"
        self.delivered.mkdir(parents=True, exist_ok=True)
        (path / "files").mkdir(parents=True, exist_ok=True)

    def has_pending(self):
        return any(self.path.glob("*.json"))

    def claim(self):
        out = []
        for p in sorted(self.path.glob("*.json")):
            target = self.delivered / p.name
            try:
                os.rename(p, target)
            except OSError:
                continue
            msg = self.read(target)
            if msg.text or msg.images:
                out.append(msg)
        return out

    def delivered_ids(self):
        return {p.name for p in self.delivered.glob("*.json")}

    def read(self, path):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return Message(path.name, "", [])
        images = [i for i in data.get("images", []) if isinstance(i, str) and self.file(i)]
        return Message(path.name, str(data.get("text", "")).strip(), images)

    def file(self, rel):
        """The host path of an image in this inbox, or None if rel points anywhere else."""
        path = (self.path / rel).resolve()
        return path if (self.path / "files").resolve() in path.parents and path.is_file() else None
