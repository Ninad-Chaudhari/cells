"""Turns a runtime's events into chat feed entries, [kind, text] or [kind, text, extra].

Kinds: say (agent text), tool (a call: name and {summary, args}), result / error (that call's output),
done (end of a turn: its answer, with echo=True when it repeats the last say and error=True when the
turn failed) and you (a message you sent). Understands Claude Code stream-json and Codex exec --json."""
import json

SUMMARY_KEYS = ("url", "command", "query", "pattern", "file_path", "path", "folder_path",
                "element", "text", "name", "function")


def short(value, limit, keep_lines=False):
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    s = s.strip() if keep_lines else " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def summary(inp):
    if not isinstance(inp, dict):
        return ""
    for k in SUMMARY_KEYS:
        if isinstance(inp.get(k), str) and inp[k].strip():
            return inp[k]
    return next((v for v in inp.values() if isinstance(v, str)), "")


def tool_entry(name, inp):
    return ["tool", name, {"summary": short(summary(inp), 240), "args": short(inp, 2000, True)}]


def unwrap_shell(command):
    """`bash -lc 'ls -la'` reads better as `ls -la`."""
    for prefix in ("bash -lc ", "/bin/bash -lc ", "bash -c ", "sh -c "):
        if command.startswith(prefix):
            inner = command[len(prefix):].strip()
            if len(inner) > 1 and inner[0] == inner[-1] and inner[0] in "'\"":
                inner = inner[1:-1]
            return inner
    return command


class Converter:
    """One per event stream: remembers which Codex calls already showed up as started."""

    def __init__(self):
        self.started = set()

    def add(self, ev, out):
        kind = ev.get("type")
        if kind in ("assistant", "user"):
            self.claude_message(ev, out)
        elif kind == "result":
            result = ev.get("result") or ""
            echo = bool(out) and out[-1][0] == "say" and out[-1][1] == short(result, 6000, True)
            out.append(["done", short(result or ev.get("subtype", ""), 8000, True),
                        {"echo": echo, "error": bool(ev.get("is_error"))}])
        elif kind == "cell_message":
            out.append(["you", short(ev.get("text", ""), 8000, True),
                        {"via": ev.get("via", ""), "images": ev.get("images", []), "at": ev.get("at")}])
        elif kind in ("item.started", "item.completed"):
            self.codex_item(kind == "item.started", ev.get("item") or {}, out)

    def claude_message(self, ev, out):
        for block in ev.get("message", {}).get("content", []) or []:
            if not isinstance(block, dict):
                continue
            t = block.get("type")
            if t == "text" and block.get("text", "").strip():
                out.append(["say", short(block["text"], 6000, True)])
            elif t == "tool_use":
                out.append(tool_entry(block.get("name", "").replace("mcp__playwright__", ""), block.get("input") or {}))
            elif t == "tool_result":
                content = block.get("content")
                if isinstance(content, list):
                    content = "\n".join(c.get("text", "[image]") for c in content if isinstance(c, dict))
                out.append(["error" if block.get("is_error") else "result", short(content or "", 3000, True)])

    def codex_item(self, started, item, out):
        call = codex_call(item)
        if call is None:
            if not started and item.get("type") == "agent_message" and (item.get("text") or "").strip():
                out.append(["say", short(item["text"], 6000, True)])
            elif not started and item.get("type") == "error":
                out.append(["error", short(item.get("message", ""), 3000, True)])
            return
        item_id = item.get("id")
        if started:
            self.started.add(item_id)
            out.append(call)
            return
        if item_id not in self.started:
            out.append(call)
        self.started.discard(item_id)
        ok, text = codex_outcome(item)
        out.append(["result" if ok else "error", short(text, 3000, True)])


def codex_call(item):
    kind = item.get("type")
    if kind == "command_execution":
        command = item.get("command") or ""
        return ["tool", "Bash", {"summary": short(unwrap_shell(command), 240), "args": short({"command": command}, 2000, True)}]
    if kind == "mcp_tool_call":
        server, tool, args = item.get("server", ""), item.get("tool", ""), item.get("arguments") or {}
        return tool_entry(tool if server == "playwright" else f"mcp__{server}__{tool}", args)
    if kind == "web_search":
        return ["tool", "WebSearch", {"summary": short(item.get("query", ""), 240), "args": ""}]
    if kind == "file_change":
        changes = item.get("changes") or []
        paths = ", ".join(c.get("path", "") for c in changes if isinstance(c, dict))
        return ["tool", "Edit", {"summary": short(paths, 240), "args": short(changes, 2000, True)}]
    return None


def codex_outcome(item):
    kind, status = item.get("type"), item.get("status")
    if kind == "command_execution":
        code = item.get("exit_code")
        return code in (0, None) and status != "failed", item.get("aggregated_output") or ("" if code in (0, None) else f"exit code {code}")
    if kind == "mcp_tool_call":
        if item.get("error"):
            return False, (item.get("error") or {}).get("message", "")
        content = (item.get("result") or {}).get("content") or []
        return status != "failed", "\n".join(c.get("text", "[image]") for c in content if isinstance(c, dict))
    return status != "failed", status or ""
