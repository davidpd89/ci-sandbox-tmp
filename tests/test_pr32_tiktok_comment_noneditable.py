"""PR hija de #32: un borrador EditText no es comentario publicado."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import tiktok_mobile_interact as tm


def node(text, kind="TextView", **fields):
    return {"text": text, "type": kind,
            "rect": {"x": 1, "y": 1, "width": 100, "height": 30},
            **fields}


def tree(*nodes):
    return {"elements": list(nodes)}


class CommentVisibility(unittest.TestCase):
    TEXT = "La novela tiene un final inesperado"

    def test_only_editable_draft_is_never_confirmation(self):
        self.assertFalse(tm._comment_visible_as_content(
            tree(node(self.TEXT, "EditText")), self.TEXT))

    def test_editable_draft_dominates_mirrored_textview(self):
        self.assertFalse(tm._comment_visible_as_content(
            tree(node(self.TEXT, "EditText"), node(self.TEXT, "TextView")), self.TEXT))

    def test_noneditable_exact_visible_comment_may_be_confirmed(self):
        self.assertTrue(tm._comment_visible_as_content(
            tree(node(self.TEXT, "TextView")), self.TEXT))

    def test_partial_substring_is_not_remote_confirmation(self):
        self.assertFalse(tm._comment_visible_as_content(
            tree(node(self.TEXT + " y varios capítulos", "TextView")), self.TEXT))

    def test_a_button_label_is_not_published_content(self):
        self.assertFalse(tm._comment_visible_as_content(
            tree(node(self.TEXT, "Button")), self.TEXT))

    def test_identifier_or_key_not_substitute_for_comment(self):
        self.assertFalse(tm._comment_visible_as_content(
            tree(node("", "TextView", identifier=self.TEXT)), self.TEXT))

    def test_empty_text_never_counts_even_if_tree_matches(self):
        self.assertFalse(tm._comment_visible_as_content(
            tree(node("", "TextView")), ""))

    def test_foreign_package_content_not_used(self):
        other = node(self.TEXT, "TextView",
                     identifier="com.android.systemui:id/foreign_label")
        self.assertFalse(tm._comment_visible_as_content(tree(other), self.TEXT))


if __name__ == "__main__":
    unittest.main()
