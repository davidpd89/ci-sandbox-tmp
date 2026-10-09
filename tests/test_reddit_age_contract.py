"""La ruta directa de Reddit también respeta el origen temporal del comentario."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reddit_comments as rc


def stamp(days):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()


class RedditDirectAgeTests(unittest.TestCase):
    def test_own_thread_incoming_comment_propagates_target_date(self):
        rows = [{"id": "t1_recent", "author": "lectora", "depth": 0,
                 "created": stamp(1), "text": "Me impresionó mucho el final del libro."}]
        plan = rc.plan_replies(rows)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["post_created_at"], rows[0]["created"])
        self.assertEqual(rc._check_own_thread_reply_age(plan[0]),
                         (True, "historial_parcial_GPT_decide_null"))

    def test_own_thread_old_comment_never_opens_browser(self):
        item = {"id": "t1_old", "post_created_at": stamp(9),
                "full": "He terminado este libro", "text": "Interesante."}
        logs = []
        self.assertFalse(rc.reply_in_thread(None, "https://example.invalid", item,
                                            log=logs.append))
        self.assertTrue(any("post_antiguo" in line for line in logs))

    def test_own_thread_missing_date_never_opens_browser(self):
        item = {"id": "t1_undated", "full": "He terminado este libro",
                "text": "Interesante."}
        logs = []
        self.assertFalse(rc.reply_in_thread(None, "https://example.invalid", item,
                                            log=logs.append))
        self.assertTrue(any("edad_desconocida" in line for line in logs))

    def test_new_external_comment_carries_original_post_date(self):
        created = stamp(0.25)
        thread = {"subreddit": "r/libros", "title": "Mi estantería de novelas",
                  "url": "https://www.reddit.com/r/libros/comments/demo/title/",
                  "author": "lectora", "comment_count": 2, "created": created,
                  "post_type": "image"}
        plan = rc.build_plan([thread], max_comments=2)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["post_created_at"], created)

    def test_unknown_external_post_date_is_not_sent_to_writer(self):
        thread = {"subreddit": "r/libros", "title": "Mi estantería de novelas",
                  "url": "https://www.reddit.com/r/libros/comments/demo/title/",
                  "author": "lectora", "comment_count": 2, "post_type": "image"}
        self.assertEqual(rc.build_plan([thread], max_comments=2), [])

    def test_secondary_profile_comment_requires_age_and_kind(self):
        old = {"url": "https://www.reddit.com/r/libros/comments/old/",
               "text": "Prueba de lectura", "post_created_at": stamp(10)}
        unknown = {"url": old["url"], "text": old["text"]}
        recent = {**old, "post_created_at": stamp(1)}
        events, logs = [], []
        publish = lambda *args: events.append(args)
        self.assertFalse(rc._publish_profile_comment(old, log=logs.append,
                                                      publish=publish))
        self.assertFalse(rc._publish_profile_comment(unknown, log=logs.append,
                                                      publish=publish))
        self.assertEqual(events, [])
        self.assertTrue(any("post_antiguo" in msg for msg in logs))
        self.assertTrue(any("edad_desconocida" in msg for msg in logs))
        self.assertTrue(rc._publish_profile_comment(recent, log=logs.append,
                                                     publish=publish))
        self.assertEqual(events, [(recent["url"], recent["text"])])

    def test_scanner_extracts_comment_not_root_creation(self):
        self.assertIn("created-timestamp", rc._JS_COMMENTS)
        self.assertIn("time[datetime]", rc._JS_COMMENTS)


if __name__ == "__main__":
    unittest.main()
