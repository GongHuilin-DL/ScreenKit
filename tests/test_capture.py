"""capture 与图片导出冒烟测试。运行: python -m unittest tests.test_capture -v"""
import sys
import unittest
from pathlib import Path

import numpy as np

from app.core.capture.screen_capture import ScreenCapture
from app.core.export.image_exporter import ImageExporter
from app.core.models import FrameResult, Rect
from app.infra.paths import TEMP_DIR


class TestRect(unittest.TestCase):
    def test_rejects_non_positive_size(self) -> None:
        with self.assertRaises(ValueError):
            Rect(0, 0, 0, 10)
        with self.assertRaises(ValueError):
            Rect(0, 0, 10, -1)

    def test_allows_negative_origin(self) -> None:
        rect = Rect(-1920, 0, 1920, 1080)
        self.assertEqual(rect.right, 0)
        self.assertEqual(rect.bottom, 1080)

    def test_to_mss_region(self) -> None:
        rect = Rect(10, 20, 300, 400)
        self.assertEqual(
            rect.to_mss_region(),
            {"left": 10, "top": 20, "width": 300, "height": 400},
        )

    def test_from_ltrb_normalizes_reverse_drag(self) -> None:
        rect = Rect.from_ltrb(500, 400, 100, 100)
        self.assertEqual((rect.x, rect.y, rect.width, rect.height), (100, 100, 400, 300))

    def test_contains(self) -> None:
        outer = Rect(0, 0, 100, 100)
        self.assertTrue(outer.contains(Rect(10, 10, 50, 50)))
        self.assertFalse(outer.contains(Rect(90, 90, 50, 50)))


@unittest.skipUnless(sys.platform == "win32", "屏幕捕获仅在 Windows 上测试")
class TestScreenCapture(unittest.TestCase):
    def test_primary_monitor_rect_valid(self) -> None:
        with ScreenCapture() as cap:
            rect = cap.primary_monitor_rect()
        self.assertGreater(rect.width, 0)
        self.assertGreater(rect.height, 0)

    def test_grab_region_matches_requested_size(self) -> None:
        region = Rect(0, 0, 200, 150)
        with ScreenCapture() as cap:
            frame = cap.grab(region)
        self.assertIsInstance(frame, FrameResult)
        self.assertEqual(frame.image.shape[:2], (150, 200))
        self.assertEqual(frame.image.shape[2], 4)  # BGRA
        self.assertEqual(frame.image.dtype, np.uint8)

    def test_grab_full_screen_when_region_none(self) -> None:
        with ScreenCapture() as cap:
            frame = cap.grab(None)
            expected = cap.primary_monitor_rect()
        self.assertEqual(frame.image.shape[:2], (expected.height, expected.width))


class TestImageExporter(unittest.TestCase):
    def _fake_bgra(self, w: int = 64, h: int = 48) -> np.ndarray:
        # 构造可预测的 BGRA 图像：B=255 的纯蓝色区域
        img = np.zeros((h, w, 4), dtype=np.uint8)
        img[:, :, 0] = 255  # B
        img[:, :, 3] = 255  # A
        return img

    def test_save_png(self) -> None:
        path = TEMP_DIR / "_test_export.png"
        try:
            saved = ImageExporter.save(self._fake_bgra(), path, fmt="png")
            self.assertTrue(saved.is_file())
            from PIL import Image
            with Image.open(saved) as im:
                self.assertEqual(im.size, (64, 48))
                # B=255 的图像在 RGB 中应该 R 接近 0，B 接近 255
                r, g, b = im.convert("RGB").getpixel((0, 0))
                self.assertLess(r, 10)
                self.assertGreater(b, 240)
        finally:
            path.unlink(missing_ok=True)

    def test_save_jpg_uses_quality(self) -> None:
        path = TEMP_DIR / "_test_export.jpg"
        try:
            saved = ImageExporter.save(self._fake_bgra(), path, fmt="jpg", quality=90)
            self.assertTrue(saved.is_file())
            self.assertGreater(saved.stat().st_size, 0)
        finally:
            path.unlink(missing_ok=True)

    def test_save_rejects_unknown_format(self) -> None:
        with self.assertRaises(ValueError):
            ImageExporter.save(self._fake_bgra(), TEMP_DIR / "_x.webp", fmt="webp")

    def test_infers_format_from_suffix(self) -> None:
        path = TEMP_DIR / "_test_infer.bmp"
        try:
            saved = ImageExporter.save(self._fake_bgra(), path)
            self.assertTrue(saved.is_file())
            self.assertEqual(saved.suffix.lower(), ".bmp")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)