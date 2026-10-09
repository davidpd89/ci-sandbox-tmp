"""meta_publish (06/10): flujos de publicacion de Facebook e Instagram sin red (se sustituyen las llamadas HTTP)."""
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import meta_publish as mp


class Resp:
    def __init__(self, data, ok=True):
        self.data, self.ok, self.status_code, self.text = data, ok, 200 if ok else 400, str(data)

    def json(self):
        return self.data


class FacebookTests(unittest.TestCase):
    def setUp(self):
        self.orig = (mp.mc.graph_post, mp.requests.post)
        self.graph, self.uploads = [], []
        mp.mc.graph_post = lambda base, path, token, **params: self.graph.append((path, params)) or {"id": "FEED1"}

        def fake_post(url, data=None, files=None, timeout=0):
            self.uploads.append((url, dict(data), files["source"][0]))
            return Resp({"id": f"PH{len(self.uploads)}", "post_id": "PAGE_POST1"})
        mp.requests.post = fake_post
        folder = tempfile.mkdtemp()
        self.paths = []
        for name in ("a.png", "b.png"):
            from PIL import Image
            path = os.path.join(folder, name)
            Image.new("RGBA", (40, 40), (255, 0, 0, 0)).save(path)
            self.paths.append(path)

    def tearDown(self):
        mp.mc.graph_post, mp.requests.post = self.orig

    def test_text_only_goes_to_feed(self):
        self.assertEqual(mp.publish_facebook("t", "PAGE", "hola"), "FEED1")
        self.assertEqual(self.graph[0][0], "PAGE/feed")

    def test_one_image_uses_photos_with_alt_and_published(self):
        post = mp.publish_facebook("t", "PAGE", "hola", self.paths[:1], ["alt"])
        self.assertEqual(post, "PAGE_POST1")
        url, data, name = self.uploads[0]
        self.assertTrue(url.endswith("PAGE/photos"))
        self.assertEqual((data["published"], data["alt_text_custom"], data["message"]), ("true", "alt", "hola"))

    def test_several_images_are_attached_to_one_feed_post(self):
        mp.publish_facebook("t", "PAGE", "hola", self.paths, ["a", "b"])
        self.assertEqual([u[1]["published"] for u in self.uploads], ["false", "false"])
        params = self.graph[0][1]
        self.assertIn('"media_fbid":"PH1"', params["attached_media[0]"])
        self.assertIn('"media_fbid":"PH2"', params["attached_media[1]"])

    def test_error_response_raises(self):
        mp.requests.post = lambda *a, **k: Resp({"error": {"message": "sin permiso"}}, ok=False)
        with self.assertRaises(RuntimeError):
            mp.publish_facebook("t", "PAGE", "hola", self.paths[:1])

    def test_public_image_is_converted_to_jpeg_and_unpublished(self):
        orig_get = mp.mc.graph_get
        mp.mc.graph_get = lambda base, path, token, **p: {"images": [{"source": "https://cdn/small.jpg", "width": 100}, {"source": "https://cdn/big.jpg", "width": 900}]}
        try:
            self.assertEqual(mp.public_image_url("t", "PAGE", self.paths[0]), "https://cdn/big.jpg")
        finally:
            mp.mc.graph_get = orig_get
        self.assertEqual(self.uploads[0][1]["published"], "false")
        self.assertTrue(self.uploads[0][2].endswith(".jpg"))


class InstagramTests(unittest.TestCase):
    def setUp(self):
        self.orig = (mp.mc.graph_post, mp.mc.graph_get)
        self.calls = []

        def post(base, path, token, **params):
            self.calls.append((path, params))
            return {"id": f"C{len(self.calls)}"}
        mp.mc.graph_post = post
        mp.mc.graph_get = lambda base, path, token, **p: {"status_code": "FINISHED"}

    def tearDown(self):
        mp.mc.graph_post, mp.mc.graph_get = self.orig

    def test_single_image(self):
        mp.publish_instagram("t", "U", "pie", ["https://x/1.jpg"], ["alt1"])
        self.assertEqual([c[0] for c in self.calls], ["U/media", "U/media_publish"])
        self.assertEqual(self.calls[0][1]["alt_text"], "alt1")
        self.assertEqual(self.calls[1][1]["creation_id"], "C1")

    def test_carousel_builds_children_then_parent(self):
        mp.publish_instagram("t", "U", "pie", ["https://x/1.jpg", "https://x/2.jpg", "https://x/3.jpg"], ["a", "b", "c"])
        paths = [c[0] for c in self.calls]
        self.assertEqual(paths, ["U/media"] * 4 + ["U/media_publish"])
        parent = self.calls[3][1]
        self.assertEqual((parent["media_type"], parent["children"]), ("CAROUSEL", "C1,C2,C3"))
        self.assertTrue(all(c[1]["is_carousel_item"] == "true" for c in self.calls[:3]))

    def test_needs_an_image_and_caption_limit(self):
        with self.assertRaises(ValueError):
            mp.publish_instagram("t", "U", "pie", [])
        with self.assertRaises(ValueError):
            mp.publish_instagram("t", "U", "x" * 2300, ["https://x/1.jpg"])


if __name__ == "__main__":
    unittest.main()
