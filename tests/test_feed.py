"""The activity feed the dashboard polls: only new entries, never half a line, final answers marked when they repeat."""
import unittest

from support import TMP, event

from server import logs


def say(text):
    return event(type="assistant", message={"content": [{"type": "text", "text": text}]})


class FeedTest(unittest.TestCase):
    def setUp(self):
        self.path = TMP / f"{self.id()}.jsonl"
        self.path.write_text("")

    def append(self, text):
        with open(self.path, "a") as fh:
            fh.write(text)

    def test_since_returns_only_what_was_added(self):
        self.append(say("one") + say("two"))
        self.assertEqual(logs.feed(self.path), (2, [["say", "one"], ["say", "two"]]))
        self.append(say("three"))
        self.assertEqual(logs.feed(self.path, since=2), (3, [["say", "three"]]))
        self.assertEqual(logs.feed(self.path, since=3), (3, []))

    def test_a_line_written_in_two_parts_appears_once_when_complete(self):
        line = say("hello world")
        self.append(line[:10])
        self.assertEqual(logs.feed(self.path), (0, []))
        self.append(line[10:])
        self.assertEqual(logs.feed(self.path), (1, [["say", "hello world"]]))

    def test_final_answer_is_marked_when_it_repeats_the_last_message(self):
        self.append(say("All done: 3 stories") + event(type="result", result="All done: 3 stories"))
        self.assertEqual(logs.feed(self.path)[1][-1], ["done", "All done: 3 stories", {"echo": True, "error": False}])

    def test_final_answer_is_not_marked_when_it_differs(self):
        self.append(say("Working on it") + event(type="result", result="Here is the table"))
        self.assertEqual(logs.feed(self.path)[1][-1], ["done", "Here is the table", {"echo": False, "error": False}])

    def test_a_replaced_stream_starts_over(self):
        self.append(say("old agent") + say("old agent again"))
        logs.feed(self.path)
        self.path.unlink()
        self.path.write_text(say("new agent"))
        self.assertEqual(logs.feed(self.path), (1, [["say", "new agent"]]))

    def test_pages_walk_back_through_history_without_gaps_or_overlap(self):
        self.append("".join(say(f"m{i}") for i in range(7)))
        start, total, last = logs.page(self.path, limit=3)
        self.assertEqual((start, total, [e[1] for e in last]), (4, 7, ["m4", "m5", "m6"]))
        start, _, older = logs.page(self.path, before=start, limit=3)
        self.assertEqual((start, [e[1] for e in older]), (1, ["m1", "m2", "m3"]))
        self.assertEqual([e[1] for e in logs.page(self.path, before=start, limit=3)[2]], ["m0"])

    def test_a_page_never_separates_a_tool_call_from_its_output(self):
        call = event(type="assistant", message={"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]})
        output = event(type="user", message={"content": [{"type": "tool_result", "content": "a.txt"}]})
        self.append(say("start") + call + output + say("end"))
        start, _, entries = logs.page(self.path, limit=2)
        self.assertEqual([e[0] for e in entries], ["tool", "result", "say"])

    def test_tool_calls_show_their_most_telling_argument(self):
        self.append(event(type="assistant", message={"content": [
            {"type": "tool_use", "name": "mcp__playwright__browser_navigate", "input": {"url": "https://example.com"}}]}))
        kind, tool, info = logs.feed(self.path)[1][0]
        self.assertEqual((kind, tool, info["summary"]), ("tool", "browser_navigate", "https://example.com"))

    def test_operator_messages_keep_their_images(self):
        self.append(event(type="cell_message", text="use this logo", images=["files/1-0.png"], via="new-turn", at=5))
        self.assertEqual(logs.feed(self.path)[1], [["you", "use this logo", {"via": "new-turn", "images": ["files/1-0.png"], "at": 5}]])


if __name__ == "__main__":
    unittest.main()
