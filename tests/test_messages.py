"""Messages from the dashboard reach the agent once, with their images, and bad ones leave nothing behind."""
import base64
import json
import os
import subprocess
import sys
import unittest

from support import ROOT, make_cell, reset

from server import agents

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
HOOK = ROOT / "bin" / "cell-inbox-hook"


def image(data=PNG, kind="image/png"):
    return {"type": kind, "data": base64.b64encode(data).decode()}


def files_in(state):
    return sorted(p.relative_to(state / "inbox").as_posix() for p in (state / "inbox").rglob("*") if p.is_file())


class MessageTest(unittest.TestCase):
    def setUp(self):
        reset()
        self.state = make_cell("writer")

    def hook(self):
        env = {**os.environ, "CELL_STATE": str(self.state), "CELLS_OWNER": "Sam"}
        out = subprocess.run([sys.executable, str(HOOK)], input="{}", env=env, capture_output=True, text=True, check=True).stdout
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.strip() else None

    def test_message_with_image_is_delivered_once(self):
        self.assertEqual(agents.queue_message("writer", "Use this logo", [image()]), (True, ""))
        first = self.hook()
        self.assertIn("New message from Sam", first)
        self.assertIn("Use this logo", first)
        saved = [f for f in files_in(self.state) if f.startswith("files/")]
        self.assertEqual(len(saved), 1)
        self.assertIn(str(self.state / "inbox" / saved[0]), first)
        self.assertIsNone(self.hook())

    def test_one_bad_image_rejects_the_message_and_writes_nothing(self):
        ok, err = agents.queue_message("writer", "two pictures", [image(), image(kind="image/svg+xml")])
        self.assertFalse(ok)
        self.assertIn("PNG", err)
        self.assertEqual(files_in(self.state), [])

    def test_oversized_image_is_refused(self):
        ok, _ = agents.queue_message("writer", "", [image(b"\0" * (8 * 1024 * 1024 + 1))])
        self.assertFalse(ok)
        self.assertEqual(files_in(self.state), [])

    def test_ended_agent_takes_no_messages(self):
        (self.state / "status").write_text("finished")
        self.assertEqual(agents.queue_message("writer", "hello?"), (False, "This agent has ended."))

    def test_empty_message_is_refused(self):
        self.assertFalse(agents.queue_message("writer", "   ", [])[0])


if __name__ == "__main__":
    unittest.main()
