"""What an agent writes, read from outside its sandbox. Inside, a cell can write only state/agent/ (its help
request and receipts for messages it was handed mid-task); the host reads those files as plain data: never
through a symlink, never a pipe or a device, and only up to a limit. The host never writes there."""
import os
import stat


def read(path, limit=64 * 1024):
    """The file's text, or None if it is missing or is not a plain file."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return None
        return fh.read(limit).decode(errors="replace")
