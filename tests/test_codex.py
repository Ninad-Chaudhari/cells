"""Codex agents: their events read as the same chat as Claude's, and their credentials stay out of files
and arguments the agent or other users could read."""
import json
import os
import stat
import tomllib
import unittest
from pathlib import Path

from support import TMP, event, make_cell, reset

from agent.cell import Cell
from agent.codex import Driver
from agent.inbox import Inbox
from server import config, logs


class CodexChatTest(unittest.TestCase):
    def setUp(self):
        self.path = TMP / f"{self.id()}.jsonl"
        self.path.write_text("")

    def chat(self, *events):
        self.path.write_text("".join(event(**e) for e in events))
        return logs.feed(self.path)[1]

    def test_a_shell_command_shows_as_one_call_with_its_output(self):
        entries = self.chat(
            {"type": "item.started", "item": {"id": "i1", "type": "command_execution", "command": "bash -lc 'ls -la'", "status": "in_progress"}},
            {"type": "item.completed", "item": {"id": "i1", "type": "command_execution", "command": "bash -lc 'ls -la'",
                                                 "aggregated_output": "notes.md", "exit_code": 0, "status": "completed"}})
        self.assertEqual([(e[0], e[1]) for e in entries], [("tool", "Bash"), ("result", "notes.md")])
        self.assertEqual(entries[0][2]["summary"], "ls -la")

    def test_a_failing_command_is_an_error(self):
        entries = self.chat({"type": "item.completed", "item": {"id": "i2", "type": "command_execution", "command": "false",
                                                                 "aggregated_output": "", "exit_code": 1, "status": "failed"}})
        self.assertEqual([e[0] for e in entries], ["tool", "error"])

    def test_browser_calls_read_like_claudes(self):
        entries = self.chat({"type": "item.completed", "item": {
            "id": "i3", "type": "mcp_tool_call", "server": "playwright", "tool": "browser_navigate",
            "arguments": {"url": "https://example.com"}, "result": {"content": [{"type": "text", "text": "Page loaded"}]},
            "status": "completed"}})
        self.assertEqual(entries[0][:2], ["tool", "browser_navigate"])
        self.assertEqual(entries[0][2]["summary"], "https://example.com")
        self.assertEqual(entries[1], ["result", "Page loaded"])

    def test_the_answer_ends_the_turn(self):
        entries = self.chat(
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "item.completed", "item": {"id": "i4", "type": "reasoning", "text": "thinking"}},
            {"type": "item.completed", "item": {"id": "i5", "type": "agent_message", "text": "Three stories."}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
            {"type": "result", "subtype": "success", "is_error": False, "result": "Three stories."})
        self.assertEqual(entries, [["say", "Three stories."], ["done", "Three stories.", {"echo": True, "error": False}]])


class CodexCredentialTest(unittest.TestCase):
    def setUp(self):
        reset()
        self.state = make_cell("coder")
        (self.state / "runtime").write_text("codex")
        os.environ.update(CELLS_APP=str(Path(__file__).resolve().parent.parent), CELLS_NODE="/usr/bin/node",
                          CELLS_PLAYWRIGHT_MCP="/opt/pw/cli.js", CELLS_OPENCONTEXT="", CELLS_CODEX="/opt/codex/bin/codex")
        os.environ.pop("CODEX_API_KEY", None)
        self.secrets = config.HOME / "secrets"
        self.secrets.mkdir(mode=0o700)
        cell = Cell.load("coder")
        cell.home.mkdir(parents=True)
        self.driver = Driver(cell, Inbox(self.state))

    def save_key(self, mode):
        key = self.secrets / "openai-api-key"
        key.write_text("sk-test-123\n")
        key.chmod(mode)

    def test_the_key_reaches_codex_through_its_environment_only(self):
        self.save_key(0o600)
        self.driver.prepare()
        self.driver.start(["bwrap", "--ro-bind", "/", "/"], self.driver.env(), None)
        self.assertEqual(self.driver.env()["CODEX_API_KEY"], "sk-test-123")
        written = "".join(p.read_text() for p in self.driver.cell.home.rglob("*") if p.is_file())
        self.assertNotIn("sk-test-123", written)
        self.assertNotIn("sk-test-123", " ".join(self.driver.argv("hi", [])))

    def test_config_keeps_credentials_in_memory_and_is_valid_toml(self):
        self.driver.prepare()
        cfg = tomllib.loads((self.driver.cell.home / ".codex" / "config.toml").read_text())
        self.assertEqual(cfg["cli_auth_credentials_store"], "ephemeral")
        self.assertEqual(cfg["mcp_servers"]["playwright"]["args"][0], "/opt/pw/cli.js")
        self.assertTrue(cfg["hooks"]["PostToolUse"][0]["hooks"][0]["command"].endswith("/.cell/bin/cell-inbox-hook"))
        self.assertEqual(stat.S_IMODE((self.driver.cell.home / ".codex").stat().st_mode), 0o700)

    def test_a_key_file_others_can_read_is_refused(self):
        self.save_key(0o644)
        with self.assertRaises(PermissionError):
            self.driver.env()

    def test_later_turns_resume_the_same_thread(self):
        self.driver.start(["bwrap"], {}, None)
        self.driver.thread = "0199-thread"
        argv = self.driver.argv("--looks like a flag", ["files/1-0.png"])
        self.assertEqual(argv[argv.index("exec") + 1], "resume")
        self.assertEqual(argv[-3:], ["--", "0199-thread", "--looks like a flag"])
        self.assertIn(f"--image={self.driver.cell.inner}/state/inbox/files/1-0.png", argv)


if __name__ == "__main__":
    unittest.main()
