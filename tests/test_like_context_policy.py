"""PR #81 — regresiones del caso visual y fallback."""
import pathlib, sys, unittest
from types import SimpleNamespace
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import like_context_policy as p

class LikePolicyTests(unittest.TestCase):
    def test_image_only_and_alt_no_like(self):
        for txt in ("", "@david", "#fantasía", "❤️", "https://example.org"):
            self.assertFalse(p.can_like(txt, media_present=True)[0])

    def test_literary_image_and_sensitive(self):
        caption = "Hoy comparto la portada de mi nueva novela de fantasía juvenil"
        self.assertTrue(p.can_like(caption, media_present=True)[0])
        self.assertFalse(p.can_like(caption, media_present=True, sensitive=True)[0])

    def test_six_networks_without_banning_legitimate_likes(self):
        for net, kind in (("x","like"),("threads","like_latest"),("facebook","like_external"),
                          ("reddit","vote"),("pinterest","react"),("tiktok","like")):
            with self.subTest(network=net):
                self.assertEqual(p.check_execution(net, {"kind":kind})[0], net not in ("pinterest", "facebook"))
                self.assertFalse(p.check_execution(net, {"kind":kind,"media_present":True})[0])
                self.assertTrue(p.check_execution(net, {"kind":kind,"media_present":True,
                    "post_text":"Hoy comparto la portada de mi nueva novela de fantasía juvenil"})[0])
                self.assertFalse(p.check_execution(net, {"kind":kind,"sensitive":True})[0])

    def test_threads_text_fragment_is_not_a_caption(self):
        self.assertTrue(p.check_execution("threads", {"kind":"like_latest","text_fragment":"adios"})[0])
        self.assertFalse(p.check_execution("threads", {"kind":"like_latest",
            "text_fragment":"fantasía","media_present":True,"media_checked":True})[0])

    def test_null_author_record_cannot_crash(self):
        self.assertFalse(p.bluesky_sensitive({"author":None,"record":None}))
        self.assertTrue(p.bluesky_sensitive({"author":None,"record":None,
                                            "labels":[{"val":"sexual"}]}))

    def test_bluesky_getposts_read_target(self):
        uri="at://did:plc:ana/app.bsky.feed.post/123"
        def ok(post):
            client=SimpleNamespace(AUTH_BASE="auth",_url_to_uri=lambda url:uri,
                 _get=lambda *args,**kwargs:{"posts":[post]})
            return p.check_execution("bluesky",{"kind":"like",
                "url":"https://bsky.app/profile/ana/post/123"},bluesky_client=client)[0]
        self.assertFalse(ok({"uri":uri,"record":{"text":"",
            "embed":{"$type":"app.bsky.embed.images","images":[{"alt":"cartel político"}]}}}))
        self.assertTrue(ok({"uri":uri,"record":{"text":
            "Hoy comparto la portada de mi nueva novela de fantasía juvenil",
            "embed":{"$type":"app.bsky.embed.images"}}}))

    def test_access_errors_403_429_denied_5xx_fallback(self):
        for code in ("403","429","503"):
            client=SimpleNamespace(AUTH_BASE="auth",_url_to_uri=lambda url:"at://a/post",
                  _get=lambda *args,**kw:(_ for _ in ()).throw(RuntimeError(code)))
            result=p.check_execution("bluesky",{"kind":"like",
                "url":"https://bsky.app/profile/a/post/1"},bluesky_client=client)
            self.assertEqual(result[0],code=="503")

    def test_401_and_invalid_json_do_not_fall_back(self):
        for error in (RuntimeError("401 Unauthorized"), ValueError("invalid json")):
            b = SimpleNamespace(AUTH_BASE="auth",
                _url_to_uri=lambda url: "at://a/post",
                _get=lambda *args, **kwargs: (_ for _ in ()).throw(error))
            self.assertFalse(p.check_execution("bluesky", {"kind": "like",
                "url": "https://bsky.app/profile/a/post/1"}, bluesky_client=b)[0])

    def test_404_and_410_do_not_fail_open(self):
        for exc in (RuntimeError("404 Not Found"), RuntimeError("410 Gone")):
            client=SimpleNamespace(AUTH_BASE="auth",_url_to_uri=lambda url:"at://a/post",
                _get=lambda *args,**kw:(_ for _ in ()).throw(exc))
            self.assertFalse(p.check_execution("bluesky",{"kind":"like",
                "url":"https://bsky.app/profile/a/post/1"},bluesky_client=client)[0])

    def test_mastodon_link_preview_with_literary_text_is_allowed(self):
        client=SimpleNamespace(
            _get=lambda path: {"id":"12","content":"Hoy comparto la portada de mi nueva novela de fantasía juvenil",
                "media_attachments":[],"card":{"url":"https://example.org/reseña"}},
            _plain_text=lambda text:text)
        self.assertTrue(p.check_execution("mastodon",{"kind":"favourite",
            "status_id":"12"},mastodon_client=client)[0])

    def test_bluesky_malformed_response_is_not_safely_approved(self):
        client=SimpleNamespace(AUTH_BASE="auth",_url_to_uri=lambda url:"at://a/post",
            _get=lambda *args,**kw:{"posts":"invalid"})
        self.assertFalse(p.check_execution("bluesky",{"kind":"like",
            "url":"https://bsky.app/profile/a/post/1"},bluesky_client=client)[0])

    def test_facebook_external_like_uses_original_scan_text(self):
        item = {"kind": "like_external", "permalink": "https://facebook.com/p/12"}
        self.assertFalse(p.check_execution("facebook", item)[0])
        item["post_text"] = "Hoy os presento mi nueva novela de fantasía juvenil"
        self.assertTrue(p.check_execution("facebook", item)[0])
        self.assertTrue(p.check_execution("facebook", {"kind": "like", "index": 0})[0])

    def test_pinterest_requires_a_real_caption_from_scan(self):
        pin = {"kind": "react", "media_present": True}
        self.assertFalse(p.check_execution("pinterest", pin)[0])
        pin["post_text"] = "Una lista de novelas juveniles de fantasía muy recomendables"
        self.assertTrue(p.check_execution("pinterest", pin)[0])

    def test_bluesky_embed_types_distinguish_images_and_cards(self):
        examples = [
            ("app.bsky.embed.images", True),
            ("app.bsky.embed.video", True),
            ("app.bsky.embed.recordWithMedia", True),
            ("app.bsky.embed.external", False),
            ("app.bsky.embed.record", False),
        ]
        for embed_type, expected in examples:
            post = {"record": {"text": "Mi novela de fantasía juvenil",
                               "embed": {"$type": embed_type}}}
            self.assertIs(p.bluesky_has_visual(post), expected)
        self.assertIsNone(p.bluesky_has_visual(
            {"record": {"embed": {"$type": "app.bsky.embed.future"}}}))
        self.assertTrue(p.can_like(
            "Hoy comparto la reseña de esta novela de fantasía",
            media_present=False)[0])
        self.assertFalse(p.can_like("Mi novela", media_present=None)[0])

    def test_non_likes_not_blocked(self):
        for net in ("bluesky","mastodon","x","threads","facebook","pinterest","reddit","tiktok"):
            self.assertEqual(p.check_execution(net,{"kind":"follow"}),(True,"accion_no_es_like"))

if __name__=="__main__":
    unittest.main()
