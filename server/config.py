"""Paths and settings, from the environment set up by bin/cells-env."""
import os
import re
import socket
from pathlib import Path

APP = Path(os.environ.get("CELLS_APP") or Path(__file__).resolve().parent.parent)
HOME = Path(os.environ.get("CELLS_HOME") or Path.home() / "cells")
SCREENS = HOME / "screens"
RUN = HOME / "run"
HISTORY = HOME / "history"
KNOWLEDGE = HOME / "knowledge"
CONTEXTS = KNOWLEDGE / "contexts"
SOCK = RUN / "dash.sock"
WEB = APP / "web"
CELL = APP / "bin" / "cell"

UNIT = os.environ.get("CELLS_UNIT", "cells")
NAME = os.environ.get("CELLS_NAME") or socket.gethostname().split(".")[0]
MAX = int(os.environ.get("CELLS_MAX", "20"))
TCP = os.environ.get("CELLS_DASH_TCP", "")

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
KEYS_RE = re.compile(r"^[A-Za-z0-9_+]{1,40}$")
HASH_RE = re.compile(r"^[0-9a-f]{4,40}$")
ARCHIVE_RE = re.compile(r"^\d{8}-\d{6}-[a-z0-9][a-z0-9-]{0,30}$")
FILE_RE = re.compile(r"^files/[0-9]+-[0-9]+\.(png|jpe?g|gif|webp)$")
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES = 6

os.environ["XAUTHORITY"] = str(RUN / "xauth")


def read(path, default=None):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default
