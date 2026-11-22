"""Supervises one agent. Runs its first turn on the task, then a new turn for each message you send once
it is idle; keeps state/status current, logs events to state/stream.jsonl and syncs the agent's copy of the
shared knowledge base before and after every turn. Messages that arrive mid-task are handed over by the
in-sandbox hook instead."""
import os
import shutil
import subprocess
import sys
import threading
import time

from . import claude, codex
from .cell import Cell
from .eventlog import EventLog
from .inbox import Inbox

DRIVERS = {"claude": claude.Driver, "codex": codex.Driver}


class Supervisor:
    def __init__(self, name, sandbox):
        self.cell = Cell.load(name)
        self.inbox = Inbox(self.cell.state / "inbox")
        self.log = EventLog(self.cell.state / "stream.jsonl")
        self.driver = DRIVERS[self.cell.runtime](self.cell, self.inbox)
        self.sandbox = [shutil.which(sandbox[0]) or sandbox[0], *sandbox[1:]]
        self.logged = self.inbox.delivered_ids()

    def status(self, value):
        (self.cell.state / "status").write_text(value + "\n")

    def sync_knowledge(self):
        """Commit this agent's knowledge edits under its name and bring its copy up to date with the others'."""
        subprocess.run([os.path.join(os.environ["CELLS_APP"], "bin", "cell-kb-commit"), self.cell.name])

    def note_hook_deliveries(self):
        """Log messages the hook handed over mid-task, so they show up in the chat."""
        while True:
            for msg_id in sorted(self.inbox.delivered_ids() - self.logged):
                self.logged.add(msg_id)
                self.log.message(self.inbox.read(self.inbox.delivered / msg_id), "during-task")
            time.sleep(1)

    def next_turn(self):
        """Wait for messages, claim them all, and return them as one turn's text and images."""
        while not self.inbox.has_pending():
            if not self.driver.alive():
                return None
            time.sleep(1)
        msgs = self.inbox.claim()
        for m in msgs:
            self.logged.add(m.id)
            self.log.message(m, "new-turn")
        if not msgs:
            return self.next_turn()
        return "\n\n".join(m.text for m in msgs if m.text), [i for m in msgs for i in m.images]

    def run(self):
        c = self.cell
        (c.state / "started").write_text(f"{int(time.time())}\n")
        self.driver.prepare()
        env = {**c.sandbox_env(), **self.driver.env()}
        with open(c.state / "stderr.log", "a") as stderr:
            self.driver.start(self.sandbox, env, stderr)
            threading.Thread(target=self.note_hook_deliveries, daemon=True).start()
            turn = ((c.state / "task.txt").read_text().strip(), [])
            while turn is not None:
                self.status("running")
                self.sync_knowledge()
                alive = self.driver.turn(*turn, self.log.write)
                self.sync_knowledge()
                if not alive:
                    break
                if not self.inbox.has_pending():
                    self.status("idle")
                turn = self.next_turn()
        code = self.driver.exit_code()
        self.status("finished" if code == 0 else f"failed ({code})")
        return code


def main():
    name = sys.argv[1]
    sandbox = sys.argv[sys.argv.index("--") + 1:]
    sys.exit(Supervisor(name, sandbox).run())
