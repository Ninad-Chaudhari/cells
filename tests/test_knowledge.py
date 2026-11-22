"""The Knowledge tab shows new docs, unsaved edits and commits as soon as they happen."""
import subprocess
import unittest

from support import reset

from server import config, knowledge


def git(*args):
    subprocess.run(["git", "-C", str(config.KNOWLEDGE), "-c", "user.name=cell scout", "-c", "user.email=c@localhost", *args],
                   check=True, capture_output=True)


class KnowledgeTest(unittest.TestCase):
    def setUp(self):
        reset()
        (config.CONTEXTS / "general").mkdir(parents=True)
        git("init", "-q")
        (config.CONTEXTS / "general" / "readme.md").write_text("# Shared notes\n")
        git("add", "-A")
        git("commit", "-qm", "start")

    def docs(self):
        return {d["path"]: (d["title"], d["dirty"]) for d in knowledge.tree()["docs"]}

    def test_new_doc_shows_as_unsaved_then_saved_after_commit(self):
        self.assertEqual(self.docs(), {"general/readme.md": ("Shared notes", False)})
        (config.CONTEXTS / "general" / "pricing.md").write_text("# Pricing pages\nThree apps compared.\n")
        self.assertEqual(self.docs()["general/pricing.md"], ("Pricing pages", True))
        git("add", "-A")
        git("commit", "-qm", "Compare pricing pages")
        self.assertEqual(self.docs()["general/pricing.md"], ("Pricing pages", False))
        self.assertEqual([(c["subject"], c["author"]) for c in knowledge.commits()][:1], [("Compare pricing pages", "cell scout")])

    def test_editing_a_doc_shows_its_new_title(self):
        self.docs()
        (config.CONTEXTS / "general" / "readme.md").write_text("# Team notes, renamed\n")
        self.assertEqual(self.docs()["general/readme.md"], ("Team notes, renamed", True))

    def test_docs_outside_the_knowledge_base_are_not_readable(self):
        (config.HOME / "secret.md").write_text("# nope")
        self.assertIsNone(knowledge.doc("../../secret.md"))
        self.assertEqual(knowledge.doc("general/readme.md")["title"], "Shared notes")


if __name__ == "__main__":
    unittest.main()
