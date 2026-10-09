"""R15: antes de unfollow en Threads, revalidar el indicador 'Te sigue'.

El usuario comprobó que una lista de seguidores incompleta NO prueba la ausencia
de followback. Las pruebas simulan exclusivamente el perfil sin tocar Edge/cuentas.
"""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import unfollow_cleanup as uc


class ThreadsFollowbackLiveCheckTests(unittest.TestCase):
    def setUp(self):
        self.ad = uc.Threads()
        self.ad.t = mock.Mock()
        self.ad.pg = mock.Mock()
        self.ad.pg.url = "https://www.threads.com/@lectora"

    def test_known_follower_does_not_require_new_page(self):
        self.ad._followers = {"lectora"}
        self.assertTrue(self.ad.follows_me("lectora"))
        self.ad.pg.goto.assert_not_called()

    def test_missing_from_partial_list_but_te_sigue_is_not_unfollowed(self):
        self.ad.t.profile_info.return_value = {"followers": 125, "follows_me": True}
        self.assertTrue(self.ad.follows_me("lectora"))
        self.ad.pg.goto.assert_called_once()
        self.ad.t.profile_info.assert_called_once_with(self.ad.pg)

    def test_loaded_profile_with_no_followback_is_allowed_to_be_candidate(self):
        self.ad.t.profile_info.return_value = {"followers": 125, "follows_me": False}
        self.assertFalse(self.ad.follows_me("lectora"))

    def test_incomplete_profile_never_counts_as_not_following(self):
        self.ad.t.profile_info.return_value = {"followers": None, "bio": "", "follows_me": False}
        with self.assertRaisesRegex(RuntimeError, "no verificable"):
            self.ad.follows_me("lectora")

    def test_wrong_profile_url_fails_closed(self):
        self.ad.pg.url = "https://www.threads.com/@otra"
        self.ad.t.profile_info.return_value = {"followers": 125, "follows_me": False}
        with self.assertRaisesRegex(RuntimeError, "perfil inesperado"):
            self.ad.follows_me("lectora")

    def test_bot_warning_is_not_swallowed(self):
        self.ad.t._check_bot_warning.side_effect = RuntimeError("aviso antibot")
        with self.assertRaisesRegex(RuntimeError, "antibot"):
            self.ad.follows_me("lectora")


if __name__ == "__main__":
    unittest.main()
