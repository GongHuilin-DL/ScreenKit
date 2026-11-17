"""拼接算法测试。运行: python -m unittest tests.test_stitcher -v"""
import importlib.util
import unittest

import numpy as np

from app.core.scrollshot.stitcher import Stitcher


def _make_strip(total_height: int, width: int = 100) -> np.ndarray:
    """逐行颜色不同的条纹图，模拟纯色/渐变页面。"""
    img = np.zeros((total_height, width, 3), dtype=np.uint8)
    for y in range(total_height):
        img[y, :, :] = y % 256
    return img


def _make_structured(total_height: int, width: int = 200, seed: int = 42) -> np.ndarray:
    """结构化图案：白色背景上随机分布矩形块。

    矩形块的边角会产生稳定的 FAST 角点，模拟真实网页中的图片、
    卡片、按钮等元素。这是 ORB 能可靠工作的合理测试数据。
    """
    rng = np.random.default_rng(seed)
    img = np.full((total_height, width, 3), 245, dtype=np.uint8)
    count = total_height // 6
    for _ in range(count):
        y = int(rng.integers(0, max(1, total_height - 16)))
        h = int(rng.integers(4, 14))
        x = int(rng.integers(0, max(1, width - 40)))
        w = int(rng.integers(20, 60))
        color = tuple(int(c) for c in rng.integers(20, 200, 3))
        img[y:min(y + h, total_height), x:min(x + w, width)] = color
    return img


class TestStitcherORB(unittest.TestCase):
    """验证 ORB 路径：使用结构化纹理，确保 ORB 能可靠估计偏移。"""

    def test_two_frames_with_known_overlap_textured(self):
        """结构化场景：ORB 应准确估计 50 行重叠。"""
        full = _make_structured(350)
        frame1 = full[0:200]     # 行 0-199
        frame2 = full[150:350]   # 行 150-349，与 frame1 重叠 50 行

        stitcher = Stitcher(prefer_scrollweave=False)
        result = stitcher.stitch([frame1, frame2])
        arr = np.array(result)
        self.assertAlmostEqual(arr.shape[0], 350, delta=5)

    def test_single_frame_returns_unchanged(self):
        frame = _make_strip(100)
        stitcher = Stitcher(prefer_scrollweave=False)
        result = stitcher.stitch([frame])
        self.assertEqual(np.array(result).shape[0], 100)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            Stitcher().stitch([])

    def test_noise_data_falls_back_safely(self):
        """纯随机噪声：ORB 一致性差，应回退或跳过，不应崩溃。"""
        rng = np.random.default_rng(7)
        f1 = rng.integers(0, 256, (200, 100, 3), dtype=np.uint8)
        f2 = rng.integers(0, 256, (200, 100, 3), dtype=np.uint8)
        stitcher = Stitcher(prefer_scrollweave=False)
        # 不要求结果精确，只要求不抛异常，且输出高度合理
        result = stitcher.stitch([f1, f2])
        arr = np.array(result)
        self.assertGreaterEqual(arr.shape[0], 200)
        self.assertLessEqual(arr.shape[0], 400)


class TestStitcherRowFingerprint(unittest.TestCase):
    """验证行指纹兜底：纯色/条纹场景 ORB 失效时仍能正确拼接。"""

    def test_two_frames_with_known_overlap_striped(self):
        full = _make_strip(350)
        frame1 = full[0:200]
        frame2 = full[150:350]

        stitcher = Stitcher(prefer_scrollweave=False)
        result = stitcher.stitch([frame1, frame2])
        arr = np.array(result)
        self.assertAlmostEqual(arr.shape[0], 350, delta=5)

    def test_identical_frames_are_skipped(self):
        frame = _make_strip(200)
        stitcher = Stitcher(prefer_scrollweave=False)
        result = stitcher.stitch([frame.copy(), frame.copy()])
        arr = np.array(result)
        self.assertEqual(arr.shape[0], 200)


class TestStitcherScrollweave(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec("scrollweave") is not None,
        "scrollweave 未安装",
    )
    def test_scrollweave_two_frames(self):
        # 两帧尺寸必须一致（真实滚动截图的视口大小固定）
        full = _make_strip(350, 120)
        frame1 = full[0:200]     # (200, 120, 3)
        frame2 = full[150:350]   # (200, 120, 3)，与 frame1 尺寸一致

        stitcher = Stitcher(prefer_scrollweave=True)
        result = stitcher.stitch([frame1, frame2], scroll_positions=[0, 150])
        arr = np.array(result)
        self.assertGreater(arr.shape[0], 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)