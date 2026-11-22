"""Which agent runtimes this host can start: installed, and with a credential on file.
Only checks that a credential exists; the dashboard never reads one."""
import os
from pathlib import Path

from .config import SECRETS

DEFAULT = os.environ.get("CELLS_RUNTIME", "claude")

RUNTIMES = {
    "claude": {"label": "Claude Code", "bin": "CELLS_CLAUDE", "install": "./install.sh",
               "files": [("CELLS_TOKEN_FILE", "claude-token")], "env": ["CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"],
               "auth": "claude setup-token, then cell auth claude"},
    "codex": {"label": "Codex", "bin": "CELLS_CODEX", "install": "./install.sh --with-codex",
              "files": [("CELLS_OPENAI_KEY_FILE", "openai-api-key"), ("CELLS_CODEX_TOKEN_FILE", "codex-access-token")],
              "env": ["CODEX_API_KEY", "CODEX_ACCESS_TOKEN"], "auth": "cell auth codex"},
}


def _installed(spec):
    path = os.environ.get(spec["bin"], "")
    return bool(path) and os.access(path, os.X_OK)


def _signed_in(spec):
    if any(os.environ.get(e) for e in spec["env"]):
        return True
    for env, name in spec["files"]:
        path = Path(os.environ.get(env) or SECRETS / name)
        try:
            if path.stat().st_size > 0:
                return True
        except OSError:
            pass
    return False


def problem(runtime):
    """Why this runtime can't start an agent, or "" when it can."""
    spec = RUNTIMES.get(runtime)
    if not spec:
        return f"Unknown runtime: {runtime}."
    if not _installed(spec):
        return f"{spec['label']} isn't installed. Run {spec['install']}."
    if not _signed_in(spec):
        return f"{spec['label']} has no credential. Run {spec['auth']}."
    return ""


def status():
    return [{"id": rid, "label": spec["label"], "default": rid == DEFAULT, "problem": problem(rid)}
            for rid, spec in RUNTIMES.items()]
