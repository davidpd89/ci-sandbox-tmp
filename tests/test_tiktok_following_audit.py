import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import tiktok_following_audit as au


def prof(lang="es", bio="", followers=500, following=300, videos=20, **extra):
    return {"language": lang, "bio": bio, "nickname": extra.get("nickname", ""), "followers": followers,
            "following": following, "videos": videos}


class ClassifyTests(unittest.TestCase):
    def verdict(self, handle="ana", profile=None, **kw):
        return au.classify(handle, profile, **kw)[0]

    def test_spanish_real_account_is_kept(self):
        self.assertEqual(self.verdict(profile=prof("es", "Amante de los libros y la lectura")), "keep")

    def test_foreign_languages_are_unfollowed(self):
        for lang in ("en", "fr", "it", "pl", "pt", "de"):
            self.assertEqual(self.verdict(profile=prof(lang, "Love books and reading")), "unfollow", lang)

    def test_spanish_bio_beats_a_wrong_ui_language(self):
        self.assertEqual(self.verdict(profile=prof("en", "Soy lectora de fantasía y escribo reseñas de libros")), "keep")

    def test_bots_are_unfollowed_even_if_spanish(self):
        self.assertEqual(self.verdict("user8574031953681", prof("es", "", 3, 40, 0)), "unfollow")
        self.assertEqual(self.verdict(profile=prof("es", "", 20, 4000, 0)), "unfollow")
        self.assertEqual(self.verdict(profile=prof("es", "", 5, 100, 0)), "unfollow")

    def test_dating_and_business_are_unfollowed(self):
        self.assertEqual(self.verdict(profile=prof("es", "Hablemos por ig, sexo y mas")), "unfollow")
        self.assertEqual(self.verdict(profile=prof("es", "Tienda online, sorteo y descuento")), "unfollow")

    def test_keep_list_and_prior_interaction_win(self):
        self.assertEqual(self.verdict("amigo", prof("en"), keep=frozenset({"amigo"})), "keep")
        self.assertEqual(self.verdict("amigo", prof("en"), interacted=True), "keep")

    def test_unreadable_profile_goes_to_review_not_unfollow(self):
        self.assertEqual(self.verdict(profile={"error": "HTTP 404"}), "review")
        self.assertEqual(self.verdict(profile=None), "review")


if __name__ == "__main__":
    unittest.main()
