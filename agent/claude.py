"""Claude Code: one long-lived `claude -p` process per cell. Each turn is a user message on its stdin;
a `result` event ends the turn. Messages sent mid-task reach it through a PostToolUse hook."""
import base64
import json
import mimetypes
import os
import subprocess

from . import secrets

LABEL = "Claude Code"


class Driver:
    def __init__(self, cell, inbox):
        self.cell = cell
        self.inbox = inbox
        self.proc = None

    def prepare(self):
        c = self.cell
        servers = {"playwright": {"command": c.node, "args": c.playwright_args()}}
        if c.opencontext:
            servers["opencontext"] = {"command": c.node, "args": [c.opencontext, "mcp"],
                                      "env": {"OPENCONTEXT_ROOT": f"{c.inner}/knowledge"}}
        hook = {"type": "command", "command": f"{c.inner}/bin/cell-inbox-hook"}
        c.config_dir.mkdir(parents=True, exist_ok=True)
        (c.config_dir / "claude-mcp.json").write_text(json.dumps({"mcpServers": servers}, indent=2))
        (c.config_dir / "claude-settings.json").write_text(
            json.dumps({"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [hook]}]}}, indent=2))

    def env(self):
        out = {"CLAUDE_CONFIG_DIR": f"{self.cell.sandbox_home}/.claude"}
        token = secrets.read("CLAUDE_CODE_OAUTH_TOKEN", "CELLS_TOKEN_FILE", "claude-token")
        if token:
            out["CLAUDE_CODE_OAUTH_TOKEN"] = token
        if os.environ.get("ANTHROPIC_API_KEY"):
            out["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]
        return out

    def start(self, sandbox, env, stderr):
        c = self.cell
        cfg = f"{c.inner}/config"
        argv = [*sandbox, os.path.realpath(os.environ["CELLS_CLAUDE"]), "-p",
                "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--dangerously-skip-permissions",
                "--settings", f"{cfg}/claude-settings.json",
                "--mcp-config", f"{cfg}/claude-mcp.json", "--strict-mcp-config",
                *(["--disallowedTools", "mcp__opencontext__oc_search"] if c.opencontext else []),
                "--append-system-prompt", c.instructions]
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                                     env=env, text=True, bufsize=1)

    def turn(self, text, images, emit):
        """Send one user message and pass every event on until the turn's result. False if the process died."""
        content = [{"type": "text", "text": text}] if text else []
        for rel in images:
            path = self.inbox.file(rel)
            if path:
                media = mimetypes.guess_type(path.name)[0] or "image/png"
                content.append({"type": "image", "source": {"type": "base64", "media_type": media,
                                                            "data": base64.b64encode(path.read_bytes()).decode()}})
        try:
            self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return False
        for line in self.proc.stdout:
            emit(line)
            if '"result"' in line:
                try:
                    if json.loads(line).get("type") == "result":
                        return True
                except ValueError:
                    pass
        return False

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def exit_code(self):
        return self.proc.wait() if self.proc else 1
