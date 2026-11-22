"""What the browser relies on: unchanged screens and state cost a 304, changed ones come through."""
import http.client
import io
import json
import threading
import unittest
from socketserver import ThreadingTCPServer
from unittest import mock

from PIL import Image

from support import make_cell, reset

from server import screens
from server.routes import Handler


class Screen:
    """Stands in for the X server: whatever color it is set to is what a capture sees."""
    color = (20, 20, 20)

    def grab(self, xdisplay=None):
        return Image.new("RGB", (1280, 800), self.color)


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingTCPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        reset()
        self.screen = Screen()
        patch = mock.patch.object(screens.ImageGrab, "grab", self.screen.grab)
        patch.start()
        self.addCleanup(patch.stop)
        screens.FRAMES.frames.clear()

    def get(self, path, etag=None):
        c = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        c.request("GET", path, headers={"If-None-Match": etag} if etag else {})
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, r.getheader("ETag"), body

    def post(self, path, body):
        c = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        c.request("POST", path, body=json.dumps(body))
        r = c.getresponse()
        out = json.loads(r.read())
        c.close()
        return r.status, out

    def test_preview_is_304_until_the_screen_changes(self):
        make_cell("web")
        status, etag, body = self.get("/shot/web?w=640")
        self.assertEqual(status, 200)
        self.assertEqual(Image.open(io.BytesIO(body)).size, (640, 400))
        screens.FRAMES.frames.clear()
        self.assertEqual(self.get("/shot/web?w=640", etag)[0], 304)
        self.screen.color = (200, 30, 30)
        screens.FRAMES.frames.clear()
        status, new_etag, _ = self.get("/shot/web?w=640", etag)
        self.assertEqual(status, 200)
        self.assertNotEqual(new_etag, etag)

    def test_preview_is_never_wider_than_the_screen(self):
        make_cell("web")
        _, _, body = self.get("/shot/web?w=4000")
        self.assertEqual(Image.open(io.BytesIO(body)).size, (1280, 800))

    def test_state_is_304_until_an_agent_changes(self):
        state = make_cell("research", task="Read the news")
        status, etag, body = self.get("/api/state")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual([(s["name"], s["status"], s["task"]) for s in data["screens"]], [("research", "running", "Read the news")])
        self.assertEqual(self.get("/api/state", etag)[0], 304)
        (state / "status").write_text("idle")
        status, _, body = self.get("/api/state", etag)
        self.assertEqual((status, json.loads(body)["screens"][0]["status"]), (200, "idle"))

    def test_a_cell_without_a_live_screen_is_not_listed(self):
        make_cell("ghost", display=233)
        (screens.X11 / "X233").unlink()
        self.assertEqual(json.loads(self.get("/api/state")[2])["screens"], [])

    def test_log_asks_the_client_to_start_over_when_the_agent_was_replaced(self):
        state = make_cell("web")
        (state / "stream.jsonl").write_text(json.dumps({"type": "result", "result": "hi"}) + "\n")
        data = json.loads(self.get("/api/log/web?since=7")[2])
        self.assertEqual((data["reset"], data["next"], [e[0] for e in data["entries"]]), (True, 1, ["done"]))

    def test_message_endpoint_queues_text(self):
        state = make_cell("web")
        self.assertEqual(self.post("/message/web", {"text": "hello"}), (200, {"ok": True, "error": ""}))
        self.assertEqual([json.loads(p.read_text())["text"] for p in (state / "inbox").glob("*.json")], ["hello"])

    def test_unknown_agent_is_404(self):
        self.assertEqual(self.get("/shot/nobody")[0], 404)
        self.assertEqual(self.post("/message/nobody", {"text": "hi"})[0], 404)


if __name__ == "__main__":
    unittest.main()
