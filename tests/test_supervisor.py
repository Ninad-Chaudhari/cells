"""The supervisor runs the task, goes idle, and turns a message you send into the agent's next turn, once.
A scripted runtime stands in for Claude Code or Codex (the boundary)."""
import json
import os
import threading
import time
import unittest
from unittest import mock

from support import TMP, make_cell, reset

from agent import supervisor
from server import inbox


class ScriptedRuntime:
    """Answers every turn with one message; the second turn is the last."""

    def __init__(self, cell, box):
        self.turns = []

    def prepare(self):
        pass

    def env(self):
        return {}

    def start(self, sandbox, env, stderr):
        pass

    def turn(self, text, images, emit):
        self.turns.append(text)
        emit(json.dumps({"type": "result", "result": f"did: {text}"}))
        return len(self.turns) < 2

    def alive(self):
        return len(self.turns) < 2

    def exit_code(self):
        return 0


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        reset()
        self.state = make_cell("helper", task="Summarize the page")
        os.environ.update(CELLS_APP=str(TMP / "app"), CELLS_NODE="/usr/bin/node")
        (TMP / "app" / "share").mkdir(parents=True, exist_ok=True)
        (TMP / "app" / "share" / "instructions.md").write_text("You are @NAME@.")
        (TMP / "app" / "bin").mkdir(exist_ok=True)
        (TMP / "app" / "bin" / "cell-kb-commit").write_text("#!/bin/sh\n")
        (TMP / "app" / "bin" / "cell-kb-commit").chmod(0o755)
        p = mock.patch.dict(supervisor.DRIVERS, {"claude": ScriptedRuntime})
        p.start()
        self.addCleanup(p.stop)

    def wait_for(self, check, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if check():
                return
            time.sleep(0.05)
        self.fail("timed out")

    def test_task_then_idle_then_a_message_becomes_the_next_turn(self):
        sup = supervisor.Supervisor("helper", ["bwrap"])
        done = threading.Thread(target=sup.run, daemon=True)
        done.start()
        self.wait_for(lambda: (self.state / "status").read_text().strip() == "idle")
        self.assertEqual(sup.driver.turns, ["Summarize the page"])
        self.assertEqual(inbox.queue_message("helper", "Now in French"), (True, ""))
        done.join(5)
        self.assertEqual(sup.driver.turns, ["Summarize the page", "Now in French"])
        stream = [json.loads(l) for l in (self.state / "stream.jsonl").read_text().splitlines()]
        notes = [e for e in stream if e["type"] == "cell_message"]
        self.assertEqual([(n["text"], n["via"]) for n in notes], [("Now in French", "new-turn")])
        self.assertEqual((self.state / "status").read_text().strip(), "finished")


if __name__ == "__main__":
    unittest.main()
