"""编码器与录制器测试。运行: python -m unittest tests.test_encoder -v"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.core.encoding.encoder_config import EncoderConfig
from app.core.encoding.pyav_encoder import PyAvEncoder
from app.core.models import Rect
from app.core.recording.recorder import Recorder


def _fake_bgra(w: int, h: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (h, w, 4), dtype=np.uint8)


class TestEncoderConfig(unittest.TestCase):
    def test_rejects_odd_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            EncoderConfig(width=101, height=100)

    def test_rejects_invalid_fps(self) -> None:
        with self.assertRaises(ValueError):
            EncoderConfig(width=100, height=100, fps=0)


class TestPyAvEncoder(unittest.TestCase):
    def test_encode_frames_and_read_back(self) -> None:
        import av

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mp4"
            cfg = EncoderConfig(width=128, height=96, fps=10, crf=30, preset="ultrafast")
            enc = PyAvEncoder(path, cfg)
            enc.open()
            for i in range(20):
                enc.write(i, _fake_bgra(128, 96, seed=i))
            enc.close()

            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)

            with av.open(str(path)) as container:
                video_streams = container.streams.video
                self.assertEqual(len(video_streams), 1)
                self.assertEqual(video_streams[0].average_rate, 10)
                frames = list(container.decode(video=0))
            self.assertEqual(len(frames), 20)

    def test_double_close_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.mp4"
            cfg = EncoderConfig(width=64, height=64, fps=10)
            enc = PyAvEncoder(path, cfg)
            enc.open()
            enc.write(0, _fake_bgra(64, 64))
            enc.close()
            enc.close()  # 不应抛异常


@unittest.skipUnless(sys.platform == "win32", "录屏测试仅在 Windows 上运行")
class TestRecorder(unittest.TestCase):
    def test_record_one_second(self) -> None:
        import av

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rec.mp4"
            region = Rect(0, 0, 320, 240)
            cfg = EncoderConfig(width=320, height=240, fps=10, preset="ultrafast")

            recorder = Recorder(region, path, cfg)
            recorder.start()
            import time
            time.sleep(1.0)
            recorder.stop()

            self.assertTrue(path.is_file())
            with av.open(str(path)) as container:
                frames = list(container.decode(video=0))
            # 1 秒 @10fps 应接近 10 帧，允许调度抖动带来的偏差
            self.assertGreaterEqual(len(frames), 7)
            self.assertLessEqual(len(frames), 13)

    def test_stop_without_start_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = EncoderConfig(width=64, height=64)
            recorder = Recorder(Rect(0, 0, 64, 64), Path(tmp) / "x.mp4", cfg)
            with self.assertRaises(RuntimeError):
                recorder.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)