"""音频模块测试。运行: python -m unittest tests.test_audio -v"""
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from app.core.audio.wav_writer import WavWriter
from app.core.export.ffmpeg_runner import FFmpegError, FFmpegRunner
from app.infra.paths import find_ffmpeg


class TestWavWriter(unittest.TestCase):
    def test_writes_int16_pcm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.wav"
            writer = WavWriter(path, sample_rate=48000, channels=2)
            writer.open()
            writer.write(np.zeros((4800, 2), dtype=np.float32))
            writer.close()

            with wave.open(str(path), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 48000)
                self.assertEqual(wf.getnframes(), 4800)

    def test_float_clipping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.wav"
            writer = WavWriter(path, 48000, 1)
            writer.open()
            data = np.array([[2.0], [-2.0]], dtype=np.float32)
            writer.write(data)
            writer.close()
            with wave.open(str(path), "rb") as wf:
                frames = wf.readframes(2)
            pcm = np.frombuffer(frames, dtype=np.int16)
            self.assertEqual(pcm[0], 32767)
            self.assertEqual(pcm[1], -32767)


@unittest.skipUnless(find_ffmpeg(), "ffmpeg 不可用，跳过合成测试")
class TestMuxer(unittest.TestCase):
    def test_mux_single_produces_audio_stream(self) -> None:
        import av

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "v.mp4"
            wav = tmp_path / "a.wav"
            out = tmp_path / "out.mp4"

            # 生成 1 秒无声视频
            from app.core.encoding.encoder_config import EncoderConfig
            from app.core.encoding.pyav_encoder import PyAvEncoder
            cfg = EncoderConfig(width=64, height=64, fps=10, preset="ultrafast")
            enc = PyAvEncoder(video, cfg)
            enc.open()
            for i in range(10):
                enc.write(i, np.zeros((64, 64, 4), dtype=np.uint8))
            enc.close()

            # 生成 1 秒静音 WAV
            writer = WavWriter(wav, 48000, 2)
            writer.open()
            writer.write(np.zeros((48000, 2), dtype=np.float32))
            writer.close()

            from app.core.export.muxer import Muxer
            Muxer().mux_single(video, wav, out)

            with av.open(str(out)) as container:
                self.assertEqual(len(container.streams.video), 1)
                self.assertEqual(len(container.streams.audio), 1)


class TestFFmpegRunner(unittest.TestCase):
    def test_missing_executable_raises(self) -> None:
        with self.assertRaises(FFmpegError):
            FFmpegRunner(executable="Z:/__not_ffmpeg__/ffmpeg.exe")


if __name__ == "__main__":
    unittest.main(verbosity=2)