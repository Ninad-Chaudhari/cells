"""Resource numbers come from the kernel's own counters: these tests stand in for /proc and /sys/fs/cgroup
(the boundary) and check the arithmetic the dashboard shows."""
import unittest
from unittest import mock

from support import TMP, event, make_cell, reset

from server import metrics, usage


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class MetricsTest(unittest.TestCase):
    def setUp(self):
        reset()
        self.root = TMP / f"kernel-{self.id()}"
        self.cg = self.root / "cgroup" / "app.slice"
        self.clock = Clock()
        for target, value in ((metrics, "CGROUP"), (metrics, "PROC")):
            p = mock.patch.object(target, value, self.root / value.lower())
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(metrics.time, "monotonic", self.clock)
        p.start()
        self.addCleanup(p.stop)
        self.m = metrics.Metrics()
        self.m.units.path = lambda unit: (self.cg / unit) if (self.cg / unit).is_dir() else None
        make_cell("web")

    def unit(self, name, current, inactive_file, usage_usec):
        d = self.cg / name
        write(d / "memory.current", f"{current}\n")
        write(d / "memory.stat", f"anon 1\ninactive_file {inactive_file}\nactive_file 5\n")
        write(d / "cpu.stat", f"usage_usec {usage_usec}\nuser_usec 1\n")
        write(d / "pids.current", "7\n")
        write(d / "memory.max", "8589934592\n")

    def cell(self):
        return self.m.snapshot()["cells"][0]

    def test_memory_is_the_working_set_of_the_agent_and_its_screen(self):
        self.unit("cells-agent-web.service", 900_000_000, 300_000_000, 0)
        self.unit("cells-screen-web.service", 60_000_000, 10_000_000, 0)
        c = self.cell()
        self.assertEqual((c["mem"], c["mem_max"], c["pids"]), (650_000_000, 8589934592, 14))

    def test_cpu_is_percent_of_one_core_between_reads(self):
        self.unit("cells-agent-web.service", 1, 0, 5_000_000)
        self.assertIsNone(self.cell()["cpu"])
        self.clock.t += 2
        self.unit("cells-agent-web.service", 1, 0, 8_000_000)
        self.assertEqual(self.cell()["cpu"], 150.0)

    def test_host_memory_used_is_total_minus_available(self):
        write(self.root / "proc" / "meminfo", "MemTotal:       16000000 kB\nMemFree:  1000 kB\nMemAvailable:   12000000 kB\n")
        host = self.m.snapshot()["host"]
        self.assertEqual(host["mem"]["used"], 4_000_000 * 1024)

    def test_host_cpu_is_busy_time_over_all_time(self):
        write(self.root / "proc" / "stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
        self.m.snapshot()
        self.clock.t += 1
        write(self.root / "proc" / "stat", "cpu  130 0 130 940 0 0 0 0 0 0\n")
        self.assertEqual(self.m.snapshot()["host"]["cpu"], 30.0)


class TokenTest(unittest.TestCase):
    def setUp(self):
        self.path = TMP / f"{self.id()}.jsonl"

    def test_claude_counts_each_message_once_even_when_repeated_per_block(self):
        usage_ = {"input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000, "output_tokens": 50}
        block = lambda t: event(type="assistant", message={"id": "msg_1", "content": [{"type": "text", "text": t}], "usage": usage_})
        self.path.write_text(block("a") + block("b") + event(type="assistant", message={"id": "msg_2", "content": [], "usage": {"input_tokens": 5, "output_tokens": 7}}))
        self.assertEqual(usage.totals(self.path), {"input": 1115, "output": 57, "cached": 1000, "reasoning": 0})

    def test_codex_adds_up_each_turn(self):
        turn = event(type="turn.completed", usage={"input_tokens": 200, "cached_input_tokens": 150, "output_tokens": 20, "reasoning_output_tokens": 8})
        self.path.write_text(turn + turn)
        self.assertEqual(usage.totals(self.path), {"input": 400, "output": 40, "cached": 300, "reasoning": 16})


if __name__ == "__main__":
    unittest.main()
