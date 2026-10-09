"""PR #81: inspección del post real en adaptadores de navegador, sin redes."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import x_interact as x
import threads_interact as t


CAPTION = "Hoy comparto la portada de mi nueva novela de fantasía juvenil"


class FakeLocator:
    def __init__(self, text="", count=0):
        self._text = text
        self._count = count
        self.first = self

    def count(self):
        return self._count

    def inner_text(self):
        return self._text


class FakeArticle:
    def __init__(self, text, with_media):
        self.text = text
        self.with_media = with_media

    def locator(self, selector):
        if selector == '[data-testid="tweetText"]':
            return FakeLocator(self.text, bool(self.text))
        if 'tweetPhoto' in selector:
            return FakeLocator(count=self.with_media)
        raise AssertionError("unexpected locator: " + selector)


class RealTargetReadTests(unittest.TestCase):
    def test_x_image_without_caption_cannot_be_liked(self):
        self.assertFalse(x._like_context_of_article(FakeArticle("", True))[0])
        self.assertFalse(x._like_context_of_article(FakeArticle("Mira esto", True))[0])

    def test_x_literary_caption_can_be_liked(self):
        self.assertTrue(x._like_context_of_article(FakeArticle(CAPTION, True))[0])
        self.assertTrue(x._like_context_of_article(FakeArticle("Gracias por recomendar ese libro", False))[0])

    def test_x_like_does_not_click_when_target_is_image_only(self):
        article = FakeArticle("", True)
        stopped = mock.Mock()
        with mock.patch.object(x, "_connect", return_value=(stopped, object())), \
             mock.patch.object(x, "_goto_status", return_value=(article, 0)):
            with self.assertRaises(x.ProfileRejected):
                x.like("https://x.com/lectora/status/123")
        stopped.stop.assert_called_once()

    def test_threads_image_without_caption_is_rejected(self):
        container = mock.Mock()
        container.inner_text.return_value = "lectora · 3 h"
        self.assertFalse(t._like_context_of_container(container)[0])

    def test_threads_literary_caption_stays_eligible(self):
        container = mock.Mock()
        container.inner_text.return_value = "lectora · 3 h " + CAPTION
        self.assertTrue(t._like_context_of_container(container)[0])



class RedditTargetTests(unittest.TestCase):
    class Post:
        def __init__(self, url, title, post_type="image", nsfw=False):
            self.attrs = {"permalink": url, "post-title": title,
                          "post-type": post_type, "nsfw": "true" if nsfw else "false"}

        def get_attribute(self, name):
            return self.attrs.get(name)

    class Nodes:
        def __init__(self, posts):
            self.posts = posts

        def count(self):
            return len(self.posts)

        def nth(self, index):
            return self.posts[index]

    def check(self, posts, target="t3_abc"):
        import reddit_interact as reddit
        page = mock.Mock()
        page.locator.return_value = self.Nodes(posts)
        return reddit._vote_context_of_post(page, target)[0]

    def test_reddit_image_without_title_is_not_upvoted(self):
        self.assertFalse(self.check([self.Post("/r/libros/comments/abc/x/", "")]))

    def test_reddit_uses_exact_target_not_another_post_in_thread(self):
        good = self.Post("/r/libros/comments/other/x/", CAPTION)
        wrong = self.Post("/r/libros/comments/abc/x/", "")
        self.assertFalse(self.check([good, wrong]))
        self.assertTrue(self.check([good, self.Post("/r/libros/comments/abc/x/", CAPTION)]))

    def test_reddit_nsfw_blocks_even_with_literary_caption(self):
        self.assertFalse(self.check([self.Post("/r/libros/comments/abc/x/", CAPTION, nsfw=True)]))


if __name__ == "__main__":
    unittest.main()
