"""转码测试。运行: python -m unittest tests.test_transcoder -v"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.core.encoding.encoder_config import EncoderConfig
from app.core.encoding.pyav_encoder import PyAvEncoder
from app.core.export.ffmpeg_runner import FFmpegRunner
from app.core.export.transcoder import Transcoder
from app.infra.paths import find_ffmpeg


def _make_test_mp4(path: Path, seconds: int = 1, fps: int = 5) -> None:
    cfg = EncoderConfig(width=64, height=64, fps=fps, preset="ultrafast")
    enc = PyAvEncoder(path, cfg)
    enc.open()
    for i in range(seconds * fps):
        enc.write(i, np.zeros((64, 64, 4), dtype=np.uint8))
    enc.close()


@unittest.skipUnless(find_ffmpeg(), "ffmpeg 不可用")
class TestTranscoder(unittest.TestCase):
    def test_mp4_to_avi(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "in.mp4"
            _make_test_mp4(src)
            out = Transcoder().transcode(src, "avi")
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 0)

    def test_mp4_to_wmv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "in.mp4"
            _make_test_mp4(src)
            out = Transcoder().transcode(src, "wmv")
            self.assertTrue(out.is_file())

    def test_unsupported_format_raises(self):
        with self.assertRaises(ValueError):
            Transcoder().transcode("x.mp4", "mkv")


if __name__ == "__main__":
    unittest.main(verbosity=2)