"""Controlling agents: start, stop, pause, resume and answer a help request."""
import json
import os
import signal
import subprocess
import threading
from pathlib import Path

from agent import untrusted

from . import inbox, runtimes
from .cells import STOPPING, cell_dir
from .config import CELL, HELP_ID_RE, NAME_RE, UNIT, read

AGENT_PROCESSES = {"claude", "codex"}


def start(name, task, images=(), runtime=None):
    """Start an agent on a task. Images go to its inbox, so it reads them as soon as it starts working."""
    name, task = (name or "").strip(), (task or "").strip()
    runtime = runtime or runtimes.DEFAULT
    if not NAME_RE.match(name):
        return False, "Name: lowercase letters, digits and dashes, up to 31 characters."
    if not task:
        return False, "Give the agent a task."
    problem = runtimes.problem(runtime)
    if problem:
        return False, problem
    _, err = inbox.decode_images(images)
    if err:
        return False, err
    r = subprocess.run([str(CELL), "up", name, task[:20000], "--runtime", runtime], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    if images:
        inbox.queue_message(name, "Images for your task.", images)
    return True, r.stdout.strip()


def stop(name):
    if name in STOPPING:
        return True

    def run():
        try:
            subprocess.run([str(CELL), "down", name], capture_output=True, timeout=180)
        finally:
            STOPPING.discard(name)

    STOPPING.add(name)
    threading.Thread(target=run, daemon=True).start()
    return True


def _agent_pids(name):
    """The agent runtime's own processes (not its browser), so you can pause it and still use the screen."""
    cg = subprocess.run(["systemctl", "--user", "show", "-p", "ControlGroup", "--value", f"{UNIT}-agent-{name}"],
                        capture_output=True, text=True, timeout=10).stdout.strip()
    if not cg:
        return []
    procs = Path("/sys/fs/cgroup" + cg)
    pids = []
    for f in [procs / "cgroup.procs", *procs.glob("**/cgroup.procs")]:
        pids += [int(p) for p in read(f, "").split() if read(Path(f"/proc/{p}/comm")) in AGENT_PROCESSES]
    return sorted(set(pids))


def set_paused(name, paused):
    d = cell_dir(name)
    pids = _agent_pids(name)
    if not d or not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGSTOP if paused else signal.SIGCONT)
        except ProcessLookupError:
            pass
    flag = d / "state" / "paused"
    if paused:
        flag.touch()
    else:
        flag.unlink(missing_ok=True)
    return True


def resolve_help(name, note):
    d = cell_dir(name)
    if not d:
        return False
    state = d / "state"
    request = state / "agent" / "help.json"
    try:
        request_id = str(json.loads(untrusted.read(request) or "{}").get("id", ""))
    except (ValueError, AttributeError):
        request_id = ""
    if HELP_ID_RE.match(request_id):
        (state / f"help-answer-{request_id}").write_text(note.strip() or "done")
    request.unlink(missing_ok=True)
    if (state / "paused").exists():
        set_paused(name, False)
    return True
