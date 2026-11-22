"""Archived runs: the list follows what's on disk, deletes stay inside the archive, files can't escape it."""
import unittest

from support import reset

from server import config, history


def archive(run_id, status="finished", task="Summarize the news", files=None):
    d = config.HISTORY / run_id
    (d / "home").mkdir(parents=True)
    (d / "status").write_text(status)
    (d / "task.txt").write_text(task)
    (d / "result.txt").write_text("Here you go")
    for rel, text in (files or {}).items():
        (d / "home" / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / "home" / rel).write_text(text)
    return d


class HistoryTest(unittest.TestCase):
    def setUp(self):
        reset()

    def test_list_is_newest_first_and_follows_adds_and_deletes(self):
        archive("20261120-090000-alpha")
        self.assertEqual([r["id"] for r in history.list_runs()], ["20261120-090000-alpha"])
        archive("20261121-100000-beta")
        self.assertEqual([r["name"] for r in history.list_runs()], ["beta", "alpha"])
        self.assertTrue(history.delete("20261121-100000-beta"))
        self.assertEqual([r["name"] for r in history.list_runs()], ["alpha"])

    def test_delete_refuses_anything_that_is_not_an_archive(self):
        config.HOME.joinpath("knowledge").mkdir(parents=True)
        archive("20261120-090000-alpha")
        for bad in ("../knowledge", "20261120-090000-alpha/..", "", "knowledge"):
            self.assertFalse(history.delete(bad), bad)
        self.assertTrue((config.HOME / "knowledge").is_dir())
        self.assertEqual(len(history.list_runs()), 1)

    def test_clear_removes_runs_and_nothing_else(self):
        archive("20261120-090000-alpha")
        archive("20261120-091500-beta")
        (config.HISTORY / "notes").mkdir()
        self.assertEqual(history.clear(), 2)
        self.assertEqual(history.list_runs(), [])
        self.assertTrue((config.HISTORY / "notes").is_dir())

    def test_files_open_only_inside_the_agents_home(self):
        d = archive("20261120-090000-alpha", files={"report.md": "# Report", ".ssh/id_ed25519": "secret"})
        (d / "status.secret").write_text("outside home")
        self.assertEqual(history.home_file("20261120-090000-alpha", "report.md").read_text(), "# Report")
        for bad in (".ssh/id_ed25519", "../status.secret", "../../knowledge", "missing.md"):
            self.assertIsNone(history.home_file("20261120-090000-alpha", bad), bad)


if __name__ == "__main__":
    unittest.main()
