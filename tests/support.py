"""Points the server at a throwaway CELLS_HOME before it is imported, and builds cells on disk."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="cells-test-"))
os.environ["CELLS_HOME"] = str(TMP / "home")
os.environ["CELLS_NAME"] = "testhost"
sys.path.insert(0, str(ROOT))

from server import cells, config  # noqa: E402

cells.X11 = TMP / "x11"


def reset():
    for d in (config.HOME, cells.X11):
        shutil.rmtree(d, ignore_errors=True)
    cells.X11.mkdir(parents=True)


def make_cell(name, display=201, status="running", task="Do the thing"):
    d = config.SCREENS / name
    state = d / "state"
    (state / "inbox").mkdir(parents=True)
    (state / "agent").mkdir()
    (d / "display").write_text(str(display))
    (state / "status").write_text(status)
    (state / "task.txt").write_text(task)
    (state / "started").write_text("1700000000")
    (cells.X11 / f"X{display}").touch()
    return state


def event(**ev):
    return json.dumps(ev) + "\n"
