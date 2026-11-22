"""A cell's inbox, written only by the host. Each message is a JSON file ({text, images, at}); its images sit
in inbox/files. A message is handed over exactly once: mid-task by the in-sandbox hook, which can only read the
inbox and lists what it handed over in state/agent/delivered, or at a new turn by the supervisor. Either way
the supervisor then files it away in inbox/delivered."""
import json
import os
import re
from typing import NamedTuple

from . import untrusted

MESSAGE_RE = re.compile(r"^[0-9]{1,24}\.json$")


class Message(NamedTuple):
    id: str
    text: str
    images: list


class Inbox:
    def __init__(self, state):
        self.path = state / "inbox"
        self.delivered = self.path / "delivered"
        self.receipts = state / "agent" / "delivered"
        self.delivered.mkdir(parents=True, exist_ok=True)
        (self.path / "files").mkdir(parents=True, exist_ok=True)

    def handed_by_hook(self):
        return {n for n in (untrusted.read(self.receipts, 1 << 20) or "").split() if MESSAGE_RE.match(n)}

    def waiting(self, handed):
        """Messages still in the inbox that the hook did (handed=True) or did not hand over."""
        names = self.handed_by_hook()
        return [p for p in sorted(self.path.glob("*.json")) if (p.name in names) == handed]

    def has_pending(self):
        return bool(self.waiting(handed=False))

    def claim(self):
        """Messages for a new turn."""
        return self.file_away(self.waiting(handed=False))

    def take_handed(self):
        """Messages the hook handed over mid-task, once each."""
        return self.file_away(self.waiting(handed=True))

    def file_away(self, paths):
        out = []
        for p in paths:
            target = self.delivered / p.name
            try:
                os.rename(p, target)
            except OSError:
                continue
            msg = self.read(target)
            if msg.text or msg.images:
                out.append(msg)
        return out

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
