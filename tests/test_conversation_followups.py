"""conversation_followups.py (02/10): respuestas sin contestar a nuestras replies."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import conversation_followups as cf

LONG = "Pues sí se me hace distinto, siendo sincero, porque el libro cavila sobre muchas cosas"


def row(handle, text=LONG, url="https://x/1"):
    return {"handle": handle, "text": text, "url": url, "mine": "mi reply"}


ASK = 'Pues sí se me hace distinto, siendo sincero, ¿a ti qué libro te pareció más pesado?'


def row(handle, text=ASK, url='https://x/1'):
    return {'handle': handle, 'text': text, 'url': url, 'mine': 'mi reply'}


class FilterTests(unittest.TestCase):
    def test_only_answers_when_they_ask_us_something(self):
        self.assertTrue(cf.worth_answering(ASK, 'ana'))
        self.assertFalse(cf.worth_answering(LONG, 'ana'))   # opinion sin pregunta: solo like

    def test_drops_bridges_short_and_opinion_requests(self):
        self.assertFalse(cf.worth_answering('¿Sí?', 'ana'))
        self.assertFalse(cf.worth_answering(ASK, 'bot.ap.brid.gy'))
        self.assertFalse(cf.worth_answering('¿Puedes leer mi novela y decirme qué te parece?', 'ana'))

    def test_answer_to_our_question_is_no_longer_answered(self):
        # 'Watching over me' contesta a nuestra pregunta: like y se acabo (hilo de la lectura conjunta, 03/10)
        self.assertFalse(cf.worth_answering('Watching over me de Iced Earth', 'ana', answers_question=True))
        items = cf.make_items([{'handle': 'pd', 'text': 'Watching over me de Iced Earth, sin duda',
                                'url': 'u', 'mine': '¿Cuál es la canción?'}])
        self.assertEqual(items, [])


class ItemsAndPlanTests(unittest.TestCase):
    def test_one_item_per_account_with_stable_ids(self):
        items = cf.make_items([row('ana'), row('ana', url='https://x/2'), row('luis', url='https://x/3')])
        self.assertEqual([(i['id'], i['handle']) for i in items], [('F01', 'ana'), ('F02', 'luis')])

    def test_live_bluesky_followup_requires_thread_and_passes_context(self):
        from unittest import mock
        import conversation_turn_policy as ctp
        rows = [{
            "handle": "ana", "text": "¿Qué libro me recomendarías para empezar?",
            "url": "https://bsky.app/profile/ana/post/1", "ref": "at://reply",
            "mine": "Yo recomiendo fantasía",
        }]
        chain = [
            {"role": "theirs", "post_id": "at://root", "text": "Busco novelas"},
            {"role": "ours", "post_id": "at://mine", "text": "Puedes probar fantasía"},
            {"role": "theirs", "post_id": "at://reply", "text": rows[0]["text"]},
        ]
        with mock.patch.object(ctp, "fetch_verified_thread", return_value=chain):
            items = cf.make_items(rows, network="bluesky", verify_threads=True)
        self.assertEqual(len(items), 1)
        self.assertIn("Historial verificado", items[0]["context"])
        with mock.patch.object(ctp, "fetch_verified_thread", return_value=[]):
            partial = cf.make_items(rows, network="bluesky", verify_threads=True)
            self.assertEqual(len(partial), 1)
            self.assertEqual(partial[0]["context_quality"], "partial")
            self.assertIn("CONTEXTO PARCIAL", partial[0]["context"])

    def test_live_followup_does_not_reopen_photo_session(self):
        from unittest import mock
        import conversation_turn_policy as ctp
        rows = [{
            "handle": "fotografo", "text": "Gracias, compañero.",
            "url": "https://bsky.app/profile/fotografo/post/1", "ref": "at://reply"
        }]
        with mock.patch.object(ctp, "fetch_verified_thread") as fetch:
            self.assertEqual(cf.make_items(rows, network="bluesky", verify_threads=True), [])
            fetch.assert_not_called()

    def test_accounts_already_answered_three_times_are_left_alone(self):
        items = cf.make_items([row('ana'), row('luis', url='u2')], replies_sent={'ana': 3, 'luis': 1})
        self.assertEqual([i['handle'] for i in items], ['luis'])

    def test_build_plan_uses_item_url_and_rejects_unknown_ids(self):
        items = cf.make_items([row('ana', url='https://x/9')])
        plan = cf.build_plan(items, {'actions': [{'id': 'F01', 'text': 'Buena idea, a mí también me pesó el segundo.'}]})
        self.assertEqual((plan[0]['url'], plan[0]['kind'], plan[0]['handle']), ('https://x/9', 'reply', 'ana'))
        with self.assertRaises(ValueError):
            cf.build_plan(items, {'actions': [{'id': 'F99', 'text': 'x'}]})

<<<<<<< HEAD
=======
    def test_followup_preserves_verified_target_date_across_two_builders(self):
        import datetime as dt
        created = "2026-10-08T10:00:00Z"
        row = {"handle": "lectora", "url": "https://example.test/post",
               "mine": "Hablábamos de novelas",
               "text": "¿Qué novela de fantasía me recomendarías?",
               "created": created}
        items = cf.make_items([row], today=dt.date(2026, 10, 9))
        self.assertEqual(items[0]["post_created_at"], created)
        plan = cf.build_plan(items, {"actions": [
            {"id": "F01", "text": "Puedes probar una fantasía juvenil breve."}]})
        self.assertEqual(plan[0]["post_created_at"], created)
        self.assertTrue(plan[0]["reply_to_us"])

>>>>>>> origin/research/public-reuse-parent
    def test_followup_text_cannot_hand_the_question_back(self):
        items = cf.make_items([row('ana')])
        with self.assertRaises(ValueError):
            cf.build_plan(items, {'actions': [{'id': 'F01', 'text': 'Buena idea. ¿Y tú?'}]})
        plan = cf.build_plan(items, {'actions': [{'id': 'F01', 'text': 'Buena idea. ¿Y tú?', 'allow_question': True}]})
        self.assertEqual(len(plan), 1)


class NotificationSourceTests(unittest.TestCase):
    DID = "did:plc:yo"

    def fake_b(self, pages):
        calls = []

        class B:
            AUTH_BASE = "auth"
            PUBLIC_BASE = "public"

            @staticmethod
            def _get(base, path, params=None, auth=True):
                calls.append(path)
                if path == "app.bsky.notification.listNotifications":
                    return pages.pop(0)
                if path == "app.bsky.feed.getPosts":
                    uris = params["uris"]
                    if base == "auth":
                        return {"posts": [{"uri": u, "viewer": {"like": "x"} if u.endswith("liked") else {}} for u in uris]}
                    return {"posts": [{"uri": u, "record": {"text": "mi post"}} for u in uris]}
                raise AssertionError(path)

            @staticmethod
            def _own_reply_parent_uris():
                return {"at://other/app.bsky.feed.post/answered"}
        return B, calls

    def note(self, rkey, reason="reply", day="2026-10-02", author="ana", did="did:plc:ana"):
        return {"reason": reason, "uri": f"at://{did}/app.bsky.feed.post/{rkey}", "indexedAt": f"{day}T10:00:00Z",
                "author": {"handle": f"{author}.bsky.social", "did": did},
                "record": {"text": "Una respuesta de prueba en español para ti", "createdAt": f"{day}T10:00:00Z"},
                "reasonSubject": "at://did:plc:yo/app.bsky.feed.post/mine"}

<<<<<<< HEAD
=======
    def test_notification_indexed_at_never_masquerades_as_post_date(self):
        import datetime
        notification = self.note("indexed")
        notification["record"].pop("createdAt")
        b, _ = self.fake_b([{"notifications": [notification], "cursor": None}])
        rows = cf.bluesky_all_notifications(b, self.DID, today=datetime.date(2026, 10, 3))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["created"], "")

>>>>>>> origin/research/public-reuse-parent
    def test_replies_become_rows_with_answered_liked_and_own_text(self):
        import datetime
        pages = [{"notifications": [self.note("n1"), self.note("liked"), {"reason": "like", "uri": "u", "indexedAt": "2026-10-02T10:00:00Z"},
                                    self.note("self", did=self.DID), self.note("ancient", day="2026-08-01")], "cursor": None}]
        b, calls = self.fake_b(pages)
        rows = cf.bluesky_all_notifications(b, self.DID, today=datetime.date(2026, 10, 3))
        by_ref = {r["ref"].rsplit("/", 1)[-1]: r for r in rows}
        self.assertEqual(set(by_ref), {"n1", "liked"})           # ni likes, ni propias, ni antiguas
        self.assertTrue(by_ref["liked"]["liked"])
        self.assertFalse(by_ref["n1"]["liked"])
        self.assertEqual(by_ref["n1"]["mine"], "mi post")
        self.assertEqual(by_ref["n1"]["url"], "https://bsky.app/profile/ana.bsky.social/post/n1")
        self.assertLessEqual(len(calls), 4)                      # 1 pagina + getPosts: barato

    def test_answered_flag_comes_from_our_reply_parents_and_paginates(self):
        import datetime
        pages = [{"notifications": [self.note("p1")], "cursor": "c1"},
                 {"notifications": [self.note("answered")], "cursor": None}]
        b, _ = self.fake_b(pages)
        rows = cf.bluesky_all_notifications(b, self.DID, today=datetime.date(2026, 10, 3))
        self.assertEqual({r["ref"].rsplit("/", 1)[-1]: r["answered"] for r in rows}, {"p1": False, "answered": False})
        # el padre respondido es la URI completa (at://other/...), aqui solo coincide si es identica:
        b2, _ = self.fake_b([{"notifications": [{**self.note("answered"), "uri": "at://other/app.bsky.feed.post/answered"}], "cursor": None}])
        rows2 = cf.bluesky_all_notifications(b2, self.DID, today=datetime.date(2026, 10, 3))
        self.assertTrue(rows2[0]["answered"])



class VisualLikeParityTests(unittest.TestCase):
    def test_image_without_post_body_rejected_even_with_alt(self):
        from unittest.mock import Mock
        rows = [{"handle": "lector", "ref": "img", "liked": False, "text": "",
                 "media_present": True, "sensitive": False}]
        liked = Mock()
        self.assertEqual(cf.like_all(rows, liked, out=lambda *_: None), (0, 0))
        liked.assert_not_called()

    def test_niche_caption_with_image_is_eligible(self):
        touched = []
        row = {"handle": "autora", "ref": "book", "liked": False,
               "text": "Hoy comparto la portada de mi nueva novela de fantasía juvenil",
               "media_present": True, "sensitive": False}
        self.assertEqual(cf.like_all([row], touched.append, out=lambda *_: None), (1, 0))
        self.assertEqual(touched, [row])

    def test_unknown_media_status_or_sensitive_label_skips(self):
        rows = [
            {"handle": "a", "ref": "one", "liked": False,
             "text": "Gracias por recomendarme este libro", "media_present": None},
            {"handle": "b", "ref": "two", "liked": False,
             "text": "Mi nueva novela de fantasía juvenil sale hoy",
             "media_present": True, "sensitive": True},
        ]
        touched = []
        self.assertEqual(cf.like_all(rows, touched.append, out=lambda *_: None), (0, 0))
        self.assertEqual(touched, [])

    def test_notification_propagates_image_and_moderation(self):
        import datetime
        source = NotificationSourceTests()
        mention = source.note("visual", reason="mention")
        mention["record"]["text"] = ""
        mention["record"]["embed"] = {
            "$type": "app.bsky.embed.images", "images": [{"alt": "propaganda"}]}
        mention["labels"] = [{"val": "sexual"}]
        client, _ = source.fake_b([{"notifications": [mention], "cursor": None}])
        rows = cf.bluesky_all_notifications(
            client, source.DID, today=datetime.date(2026, 10, 3))
        self.assertEqual(rows[0]["media_present"], True)
        self.assertEqual(rows[0]["sensitive"], True)
        touched = []
        self.assertEqual(cf.like_all(rows, touched.append, out=lambda *_: None), (0, 0))
        self.assertEqual(touched, [])

    def test_null_notification_page_entry_is_ignored(self):
        import datetime
        source = NotificationSourceTests()
        client, _ = source.fake_b([{"notifications": [source.note("ok"), None], "cursor": None}])
        rows = cf.bluesky_all_notifications(
            client, source.DID, today=datetime.date(2026, 10, 3))
        self.assertEqual(len(rows), 1)

    def test_missing_record_does_not_crash_notification(self):
        import datetime
        source = NotificationSourceTests()
        mention = source.note("empty", reason="mention")
        mention["record"] = None
        client, _ = source.fake_b([{"notifications": [mention], "cursor": None}])
        rows = cf.bluesky_all_notifications(
            client, source.DID, today=datetime.date(2026, 10, 3))
        self.assertEqual(rows[0]["media_present"], None)
        self.assertEqual(rows[0]["text"], "")

    def test_likeable_text_parity_with_shared_policy(self):
        import like_context_policy as lcp
        for text in ("", "https://example.com #libros @autor",
                     "Gracias por recomendar ese libro de fantasía",
                     "Vota en las próximas elecciones"):
            with self.subTest(text=text):
                self.assertEqual(cf.likeable_text(text),
                                 lcp.can_like(text, media_present=False)[0])

if __name__ == "__main__":
    unittest.main()


class LikeAllTests(unittest.TestCase):
    def rows(self):
        return [
            {"handle": "ana", "text": "Qué buena idea, me apunto", "ref": "1", "liked": False, "answered": False},
            {"handle": "luis", "text": "Qué buena idea, me apunto", "ref": "2", "liked": True, "answered": False},
            {"handle": "bot.ap.brid.gy", "text": "Qué buena idea, me apunto", "ref": "3", "liked": False, "answered": False},
            {"handle": "eva", "text": "Qué buena idea, me apunto", "ref": "1", "liked": False, "answered": True},
            {"handle": "kim", "text": "Qué buena idea, me apunto", "ref": "4", "liked": False, "answered": True},
        ]

    def test_likes_every_unliked_reply_once_even_if_already_answered(self):
        liked = []
        done, failed = cf.like_all(self.rows(), lambda r: liked.append(r["ref"]), out=lambda *_: None)
        self.assertEqual((done, failed, liked), (2, 0, ["1", "4"]))

    def test_failure_is_counted_and_rate_limit_stops(self):
        def boom(row):
            raise RuntimeError("HTTP 429 rate limit")
        done, failed = cf.like_all(self.rows(), boom, out=lambda *_: None)
        self.assertEqual((done, failed), (0, 1))


class LikeOnlyReadableTextTests(unittest.TestCase):
    def test_image_only_or_political_replies_are_not_liked(self):
        import conversation_followups as cf
        rows = [
            {"handle": "solo_imagen", "ref": "r1", "liked": False, "text": ""},
<<<<<<< HEAD
            {"handle": "mencion_imagen", "ref": "r2", "liked": False, "text": "@autorademo https://t.co/x #arte"},
=======
            {"handle": "mencion_imagen", "ref": "r2", "liked": False, "text": "@davidporto https://t.co/x #arte"},
>>>>>>> origin/research/public-reuse-parent
            {"handle": "politica", "ref": "r3", "liked": False, "text": "Vota al partido en las elecciones generales"},
            {"handle": "lectora", "ref": "r4", "liked": False, "text": "Me ha encantado tu reseña, gracias"},
        ]
        liked = []
        done, failed = cf.like_all(rows, lambda row: liked.append(row["handle"]), out=lambda *_: None)
        self.assertEqual(liked, ["lectora"])
        self.assertEqual((done, failed), (1, 0))
