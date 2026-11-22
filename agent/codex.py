"""Codex: one `codex exec --json` process per turn, inside a fresh sandbox; later turns resume the same
thread. Messages sent mid-task reach it through a PostToolUse hook. At the end of every turn this driver
writes a `result` event (the last agent message), so archives and the dashboard treat both runtimes alike."""
import json
import os
import subprocess

from . import secrets

LABEL = "Codex"


def toml(value):
    """A TOML value. JSON strings and arrays of strings are valid TOML."""
    return json.dumps(value) if isinstance(value, (str, list)) else str(value).lower()


class Driver:
    def __init__(self, cell, inbox):
        self.cell = cell
        self.inbox = inbox
        self.thread_file = cell.state / "codex-thread"
        self.thread = self.thread_file.read_text().strip() if self.thread_file.exists() else ""

    def prepare(self):
        c = self.cell
        model = os.environ.get("CELLS_CODEX_MODEL", "")
        lines = [
            f"developer_instructions = {toml(c.instructions)}",
            'cli_auth_credentials_store = "ephemeral"',
            "check_for_update_on_startup = false",
            *([f"model = {toml(model)}"] if model else []),
            "", "[analytics]", "enabled = false",
            "", "[history]", 'persistence = "none"',
            "", "[features]", "hooks = true",
            "", "[mcp_servers.playwright]", f"command = {toml(c.node)}", f"args = {toml(c.playwright_args())}",
            "startup_timeout_sec = 60", "tool_timeout_sec = 180",
        ]
        if c.opencontext:
            lines += ["", "[mcp_servers.opencontext]", f"command = {toml(c.node)}", f"args = {toml([c.opencontext, 'mcp'])}",
                      'disabled_tools = ["oc_search"]',
                      "", "[mcp_servers.opencontext.env]", f"OPENCONTEXT_ROOT = {toml(c.inner + '/knowledge')}"]
        lines += ["", "[[hooks.PostToolUse]]", "", "[[hooks.PostToolUse.hooks]]", 'type = "command"',
                  f"command = {toml(c.inner + '/bin/cell-inbox-hook')}", "timeout = 15", ""]
        home = c.home / ".codex"
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
        (home / "config.toml").write_text("\n".join(lines))

    def env(self):
        out = {"CODEX_HOME": f"{self.cell.sandbox_home}/.codex"}
        key = secrets.read("CODEX_API_KEY", "CELLS_OPENAI_KEY_FILE", "openai-api-key")
        token = "" if key else secrets.read("CODEX_ACCESS_TOKEN", "CELLS_CODEX_TOKEN_FILE", "codex-access-token")
        if key:
            out["CODEX_API_KEY"] = key
        elif token:
            out["CODEX_ACCESS_TOKEN"] = token
        return out

    def start(self, sandbox, env, stderr):
        self.sandbox, self.env_vars, self.stderr = sandbox, env, stderr

    def argv(self, prompt, images):
        argv = [*self.sandbox, os.path.realpath(os.environ["CELLS_CODEX"]), "exec"]
        if self.thread:
            argv.append("resume")
        argv += ["--json", "--skip-git-repo-check",
                 "--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust"]
        argv += [f"--image={self.cell.inner}/state/inbox/{rel}" for rel in images]
        return argv + ["--", *([self.thread] if self.thread else []), prompt]

    def turn(self, text, images, emit):
        prompt = text or "Look at the attached image."
        proc = subprocess.Popen(self.argv(prompt, images), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=self.stderr, env=self.env_vars, text=True, bufsize=1)
        last, problem, completed = "", "", False
        for line in proc.stdout:
            emit(line)
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            kind = ev.get("type")
            item = ev.get("item") or {}
            if kind == "thread.started" and ev.get("thread_id"):
                self.thread = ev["thread_id"]
                self.thread_file.write_text(self.thread + "\n")
            elif kind == "item.completed" and item.get("type") == "agent_message":
                last = item.get("text") or last
            elif kind == "turn.completed":
                completed = True
            elif kind == "turn.failed":
                problem = (ev.get("error") or {}).get("message") or "The turn failed."
            elif kind == "error":
                problem = ev.get("message") or problem
        code = proc.wait()
        failed = not completed and (problem or f"Codex exited with code {code}.")
        emit(json.dumps({"type": "result", "subtype": "error" if failed else "success", "is_error": bool(failed),
                         "result": failed if failed else last}))
        return True

    def alive(self):
        return True

    def exit_code(self):
        return 0
