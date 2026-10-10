"""
Pruebas unitarias y diferenciales para los adaptadores nativos de evidencia contextual (9 redes x 3 colas).
"""

import unittest
from tools.native_context_adapters import (
    adapt_native_observation,
    strip_html_tags,
    ContextPacket,
    SUPPORTED_NETWORKS,
    SUPPORTED_QUEUES,
)


class TestNativeContextAdapters(unittest.TestCase):

    def test_all_networks_and_queues_differential(self):
        sample_payloads = {
            "bluesky": {
                "uri": "at://did:plc:1234/app.bsky.feed.post/3k123",
                "author": {"handle": "fantasia.bsky.social", "displayName": "Lectora Fantasía"},
                "record": {
                    "text": "¿Alguna recomendación de romantasy en español para este otoño?",
                    "createdAt": "2026-10-09T14:30:00Z",
                    "embed": {"images": [{"thumb": "https://bsky.app/img/1.jpg", "alt": "Portada de libro"}]}
                },
                "reply": {"parent": {"uri": "at://did:plc:1234/app.bsky.feed.post/3k122", "author": {"handle": "autor.bsky.social"}}}
            },
            "mastodon": {
                "id": "1122334455",
                "account": {"acct": "lectora_fantasía@fediverse.org", "display_name": "Lectora Fantasía"},
                "content": "<p>¿Qué opináis de las sagas largas de fantasía épica? #LecturaEspañol &amp; romantasy</p>",
                "created_at": "2026-10-09T15:00:00.000Z",
                "url": "https://fediverse.org/@lectora_fantasia/1122334455",
                "in_reply_to_id": "1122334000",
                "media_attachments": [{"type": "image", "url": "https://fediverse.org/media/1.png", "description": "Libros en estantería"}]
            },
            "x": {
                "id_str": "1840000000000000000",
                "user": {"screen_name": "romantasy_es", "name": "Romantasy en Español"},
                "full_text": "Buscando novedades de literatura fantástica en español con toque de romance. ✨",
                "created_at": "Fri Oct 09 16:00:00 +0000 2026",
                "in_reply_to_status_id_str": "1839999999999999999",
                "extended_entities": {"media": [{"type": "photo", "media_url_https": "https://pbs.twimg.com/media/1.jpg"}]}
            },
            "threads": {
                "id": "334455667788",
                "user": {"username": "club_lectura_fantasía", "full_name": "Club Fantasía"},
                "caption": {"text": "Debate del mes: ¿Sistemas de magia duros o blandos?"},
                "taken_at": 1791561600,
                "code": "Cx12345678",
                "image_versions2": {"candidates": [{"url": "https://threads.net/img/1.jpg"}]}
            },
            "facebook": {
                "id": "1000112233_9988776655",
                "from": {"id": "1000112233", "name": "Grupo Lectores Fantásticos"},
                "message": "¿Alguien más leyendo fantasía en español este fin de semana?",
                "created_time": "2026-10-09T17:00:00+0000",
                "permalink_url": "https://facebook.com/groups/lectores/posts/9988776655/",
                "attachments": {"data": [{"type": "photo", "url": "https://fb.com/img/1.jpg", "title": "Estantería llena"}]}
            },
            "pinterest": {
                "id": "9876543210123",
                "pinner": {"username": "fantasialiteraria", "full_name": "Fantasía Literaria"},
                "title": "Top 10 Libros de Romantasy en Español",
                "description": "Una selección imprescindible con magia, dragones y cortes de hadas.",
                "created_at": "2026-10-09T18:00:00Z",
                "media": {"images": {"originals": {"url": "https://pinterest.com/pin/1.jpg"}}}
            },
            "reddit": {
                "name": "t3_1a2b3c4",
                "author": "LectorNocturno",
                "title": "¿Recomendaciones de fantasía urbana ambientada en España?",
                "selftext": "Busco libros similares a las sagas de fantasía moderna contemporánea.",
                "created_utc": 1791568800,
                "permalink": "/r/libros/comments/1a2b3c4/recomendaciones_fantasía/",
                "url": "https://i.redd.it/1a2b3c4.jpg"
            },
            "tiktok": {
                "id": "7300000000000000000",
                "author": {"unique_id": "booktok_espanol", "nickname": "BookTok Español"},
                "desc": "Mis 3 lecturas de fantasía favoritas de este año 📚✨ #romantasy",
                "create_time": 1791572400,
                "video": {"cover": "https://tiktok.com/cover/1.jpg"}
            },
            "instagram": {
                "id": "17900000000000000",
                "user": {"username": "reseñas_fantasía", "full_name": "Reseñas Fantásticas"},
                "caption": {"text": "Reseña de la semana: magos, conspiraciones y batallas épicas."},
                "taken_at": 1791576000,
                "code": "CzA1B2C3",
                "display_url": "https://instagram.com/p/1.jpg"
            }
        }

        for net in SUPPORTED_NETWORKS:
            for q in SUPPORTED_QUEUES:
                raw = sample_payloads[net]
                packet = adapt_native_observation(net, q, raw)

                self.assertIsInstance(packet, ContextPacket)
                self.assertEqual(packet.network, net)
                self.assertEqual(packet.queue, q)
                self.assertTrue(packet.remote_id)
                self.assertTrue(packet.author_handle)
                self.assertTrue(packet.published_at_iso)
                self.assertTrue(packet.text or packet.body)
                self.assertGreaterEqual(packet.completeness_score, 0.7)
                self.assertEqual(packet.missing_fields, [])

    def test_explicit_missing_fields_when_data_absent(self):
        incomplete_payload = {
            "uri": "at://did:plc:1234/app.bsky.feed.post/incomplete123",
            "record": {
                "text": "Comentario suelto sin fecha ni autor claro"
            }
        }
        packet = adapt_native_observation("bluesky", "api", incomplete_payload)

        self.assertIn("author_handle", packet.missing_fields)
        self.assertIn("published_at_iso", packet.missing_fields)
        self.assertIsNone(packet.author_handle)
        self.assertIsNone(packet.published_at_iso)
        self.assertLess(packet.completeness_score, 0.7)

    def test_visual_only_media_without_inventing_descriptions(self):
        visual_payload = {
            "id": "7300000000000000001",
            "author": {"unique_id": "solo_visual_creator"},
            "create_time": 1791572400,
            "video": {"cover": "https://tiktok.com/cover/visual.jpg"}
        }
        packet = adapt_native_observation("tiktok", "mobile", visual_payload)

        self.assertIn("text", packet.missing_fields)
        self.assertEqual(len(packet.media), 1)
        self.assertIsNone(packet.media[0]["alt"])
        self.assertEqual(packet.media[0]["provenance"], "https://tiktok.com/cover/visual.jpg")

    def test_unicode_and_date_handling(self):
        payload = {
            "id": "12345",
            "account": {"acct": "lector_fantasia_ñ"},
            "content": "<p>Texto con acentos y caracteres especiales: Ramón Díaz, fantasía &amp; romantasy ✨</p>",
            "created_at": "2026-10-09 20:15:30"
        }
        packet = adapt_native_observation("mastodon", "web", payload)
        self.assertIn("fantasía & romantasy", packet.text)
        self.assertEqual(packet.published_at_iso, "2026-10-09T20:15:30Z")

    def test_non_dict_payload_raises_type_error(self):
        with self.assertRaises(TypeError):
            adapt_native_observation("x", "api", None)

        with self.assertRaises(TypeError):
            adapt_native_observation("mastodon", "web", ["invalid_list"])

    def test_html_stripping_and_unescaping(self):
        raw = "<div>Hola &amp; bienvenido a <b>Fantasía</b><br>¿Qué lees?</div>"
        clean = strip_html_tags(raw)
        self.assertEqual(clean, "Hola & bienvenido a Fantasía ¿Qué lees?")

    def test_instagram_carousel_media_support(self):
        payload = {
            "id": "carousel_123",
            "user": {"username": "lectora_carousel"},
            "caption": {"text": "Carrusel de lecturas"},
            "taken_at": 1791576000,
            "carousel_media": [
                {"display_url": "https://instagram.com/p/c1.jpg", "media_type": 1},
                {"display_url": "https://instagram.com/p/c2.mp4", "media_type": 2}
            ]
        }
        packet = adapt_native_observation("instagram", "api", payload)
        self.assertEqual(len(packet.media), 2)
        self.assertEqual(packet.media[0]["type"], "image")
        self.assertEqual(packet.media[1]["type"], "video")


if __name__ == "__main__":
    unittest.main()
