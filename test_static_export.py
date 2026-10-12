import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from static_export import ExportSettings, Presets, export_image, unique_destination, write_report


class StaticExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "input.png"
        Image.new("RGBA", (100, 60), (220, 10, 40, 120)).save(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_static_formats_are_valid_and_jpeg_flattens_alpha(self):
        expected = {"webp": "WEBP", "jpeg": "JPEG", "png": "PNG"}
        for fmt, pillow_format in expected.items():
            with self.subTest(fmt=fmt):
                record = export_image(self.source, self.root / f"out.{fmt}", ExportSettings(format=fmt, quality=87))
                with Image.open(record["destination"]) as result:
                    self.assertEqual(result.format, pillow_format)
                    self.assertEqual(result.size, (100, 60))
                    if fmt == "jpeg": self.assertEqual(result.mode, "RGB")

    def test_resize_collision_and_report(self):
        record = export_image(self.source, self.root / "out.webp", ExportSettings(max_width=40, max_height=40))
        self.assertEqual(record["size"], [40, 24])
        self.assertEqual(unique_destination(self.root, self.source, "webp").name, "input.webp")
        (self.root / "input.webp").write_bytes(b"old")
        self.assertEqual(unique_destination(self.root, self.source, "webp").name, "input-2.webp")
        report = write_report(self.root, [record], [], ExportSettings())
        data = json.loads(report.read_text())
        self.assertEqual(data["format"], "singularity.export-report.v1")
        self.assertEqual(data["success"], 1)

    def test_custom_preset_round_trips(self):
        store = Presets(self.root / "presets.json")
        store.save("Mes fiches", ExportSettings("jpeg", 91, 1800, 1800))
        self.assertEqual(store.load()["Mes fiches"].quality, 91)


if __name__ == "__main__":
    unittest.main()
