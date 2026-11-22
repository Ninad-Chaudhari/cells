"""Credentials live in files only the owner can read, under $CELLS_HOME/secrets, which no sandbox can see.
They reach a runtime through its process environment (never its arguments, which any user can list)."""
import os
from pathlib import Path


def read(env_name, file_env, default_name):
    """The credential from the environment if set there, else from its secrets file, else ""."""
    if os.environ.get(env_name):
        return os.environ[env_name]
    path = Path(os.environ.get(file_env) or Path(os.environ["CELLS_HOME"]) / "secrets" / default_name)
    try:
        if path.stat().st_mode & 0o077:
            raise PermissionError(f"{path} must be readable only by you: chmod 600 {path}")
        return path.read_text().strip()
    except FileNotFoundError:
        return ""
