"""state/stream.jsonl: the runtime's own events, plus a cell_message line for each message you sent."""
import json
import threading
import time


class EventLog:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()

    def write(self, line):
        with self.lock, open(self.path, "a") as fh:
            fh.write(line if line.endswith("\n") else line + "\n")

    def message(self, msg, via):
        self.write(json.dumps({"type": "cell_message", "from": "operator", "text": msg.text, "images": msg.images,
                               "via": via, "at": int(time.time())}))
