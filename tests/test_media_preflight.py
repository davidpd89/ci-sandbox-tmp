"""Pruebas hermeticas para el preflight de nueve redes: solo bytes sinteticos."""
from __future__ import annotations

import copy
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import media_preflight as mp
import content_publisher as publisher


class MediaPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def image(self, name="foto.jpg", size=(1200, 1200), color="red"):
        path = self.root / name
        with Image.new("RGB", size, color) as im:
            im.save(path)
        return path

    def test_nine_networks_have_identical_base_contract(self):
        path = self.image()
        for net in sorted(mp.NETWORKS):
            with self.subTest(red=net):
                r = mp.inspect_asset(path, net, alt="Una lectora sostiene un libro", root=self.root)
                self.assertEqual(r["errors"], [])
                self.assertEqual(r["kind"], "image")
                self.assertIn("sha256", r["metadata"])
                self.assertEqual(r["metadata"]["width"], 1200)

    def test_missing_alt_blocks_all_nine(self):
        photo = self.image()
        for net in mp.NETWORKS:
            r = mp.inspect_asset(photo, net, root=self.root)
            self.assertIn("alt_missing", [e["code"] for e in r["errors"]])

    def test_wrong_extension_and_corrupt_bytes(self):
        unknown = self.root / "payload.exe"
        unknown.write_bytes(b"no image")
        self.assertEqual(mp.inspect_asset(unknown, "x")["errors"][0]["code"], "unknown_type")
        corrupt = self.root / "falsa.jpg"
        corrupt.write_bytes(b"un JPG falso")
        self.assertIn("image_corrupt", [e["code"] for e in mp.inspect_asset(corrupt, "threads", alt="algo")["errors"]])

    def test_outside_root_and_symlink_escape(self):
        parent = self.root.parent / "otro-archivo-ci-preflight.jpg"
        # No se crea nada fuera del directorio: la ruta ya debe rechazarse.
        self.assertEqual(mp.inspect_asset(parent, "reddit", root=self.root)["errors"][0]["code"], "unsafe_path")
        inside = self.image()
        nested = self.root / "sub"
        nested.mkdir()
        linked = nested / "alias.jpg"
        try:
            linked.symlink_to(parent)
        except (OSError, NotImplementedError):
            pass
        else:
            self.assertEqual(mp.inspect_asset(linked, "x", root=self.root)["errors"][0]["code"], "unsafe_path")
        self.assertEqual(mp.inspect_asset(inside, "reddit", alt="portada", root=self.root)["errors"], [])

    def test_file_limit_is_configurable_and_protocol_limit(self):
        photo = self.image(name="foto.png")
        size = photo.stat().st_size
        r = mp.inspect_asset(photo, "bluesky", alt="Foto", max_bytes=size - 1)
        self.assertIn("file_size", [e["code"] for e in r["errors"]])
        self.assertEqual(mp.inspect_asset(photo, "mastodon", alt="Foto")["errors"], [])

    def test_animated_media_must_not_be_silently_flattened(self):
        path = self.root / "animado.gif"
        Image.new("RGB", (100, 100), "red").save(path, save_all=True,
            append_images=[Image.new("RGB", (100, 100), "blue")], duration=100, loop=0)
        codes = [e["code"] for e in mp.inspect_asset(path, "tiktok", alt="Animacion")["errors"]]
        self.assertIn("image_format", codes)
        self.assertIn("animated", codes)
        with self.assertRaises(ValueError):
            mp.prepare_image(path, self.root / "flat.jpg")

    def test_prepare_image_preserves_source_and_ratio_no_crop(self):
        source = self.image(name="vertical.png", size=(800, 1200))
        source_bytes = source.read_bytes()
        result = mp.prepare_image(source, self.root / "lista.jpg", max_side=600)
        with Image.open(result) as im:
            self.assertEqual(im.size, (400, 600))
            self.assertEqual(im.format, "JPEG")
            self.assertFalse(im.getexif())
        self.assertEqual(source.read_bytes(), source_bytes)
        with self.assertRaises(ValueError):
            mp.prepare_image(source, source)

    def test_prepare_transparent_image_composites_and_thumbnail(self):
        path = self.root / "overlay.png"
        Image.new("RGBA", (500, 400), (255, 0, 0, 0)).save(path)
        out = mp.prepare_image(path, self.root / "blanco.jpeg")
        with Image.open(out) as im:
            self.assertEqual(im.getpixel((1, 1)), (255, 255, 255))
        preview = mp.thumbnail(path, self.root / "mini.jpg", (50, 50))
        with Image.open(preview) as im:
            self.assertEqual(im.size, (50, 40))

    def test_dedup_exact_visual_and_non_mutation(self):
        a = self.image("a.jpg", color="red")
        b = self.root / "b.jpg"
        b.write_bytes(a.read_bytes())
        c = self.image("c.jpg", color="red")
        reports = [mp.inspect_asset(f, "facebook", alt="Foto") for f in (a, b, c)]
        before = copy.deepcopy(reports)
        duplicates = mp.find_duplicates(reports)
        self.assertEqual(duplicates[0]["kind"], "exact")
        self.assertEqual(duplicates[0]["second"], "b.jpg")
        self.assertIn(duplicates[1]["kind"], {"exact", "visual_candidate"})
        self.assertEqual(reports, before)

    def test_no_ffprobe_is_unverified_not_pass(self):
        path = self.root / "video.mp4"
        path.write_bytes(b"falso video")
        with patch.object(mp.shutil, "which", return_value=None):
            r = mp.inspect_asset(path, "instagram")
        self.assertIn("video_unverified", [e["code"] for e in r["errors"]])

    def test_probe_tracks_good_bad_and_missing_without_process(self):
        path = self.root / "video.mp4"
        path.write_bytes(b"contenido sintetico")
        for codec, expected in (("h264", None), ("vp9", "video_codec")):
            with patch.object(mp, "_probe_video", return_value={
                "streams": [{"codec_type": "video", "codec_name": codec, "width": 1080, "height": 1920}],
                "format": {"duration": "12.00"},
            }):
                r = mp.inspect_asset(path, "x")
                errors = [e["code"] for e in r["errors"]]
                self.assertEqual("video_codec" in errors, expected is not None)

    def test_publisher_blocks_media_before_any_adapter_call(self):
        bad = self.root / "portada.png"
        bad.write_bytes(b"imagen ilegible")
        md = self.root / "publicacion.md"
        item = {
            "red": "bluesky", "carpeta": str(self.root), "md_path": str(md),
            "fecha_hora": __import__("datetime").datetime(2026, 10, 10),
            "estado": "lista.", "texto": "Una lectura reciente",
            "media": [{"filename": bad.name, "path": str(bad), "exists": True, "alt": "portada"}],
            "blockers": [], "meta": {},
        }
        before = copy.deepcopy(item)
        reasons = publisher.blockers_of(item, {}, __import__("datetime").datetime(2026, 10, 10))
        self.assertIn("image_corrupt", " ".join(reasons))
        self.assertEqual(item, before)
        self.assertEqual(bad.read_bytes(), b"imagen ilegible")

    def test_publisher_blocks_path_escape(self):
        item = {"red": "facebook", "carpeta": str(self.root / "sub"),
                "md_path": "ficha.md", "fecha_hora": __import__("datetime").datetime(2026, 10, 10),
                "estado": "lista.", "texto": "Texto", "meta": {}, "blockers": [],
                "media": [{"filename": "a.jpg", "path": str(self.image()), "exists": True, "alt": "Foto"}]}
        self.assertIn("unsafe_path", " ".join(publisher.blockers_of(item, {}, item["fecha_hora"])))


if __name__ == "__main__":
    unittest.main()
