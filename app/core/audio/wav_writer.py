"""WAV 写入封装：标准库 wave，固定 16-bit PCM，分块写入避免内存膨胀。"""
import wave
from pathlib import Path
from typing import BinaryIO

import numpy as np

from app.infra.logger import get_logger

logger = get_logger("audio.wav_writer")


class WavWriter:
    """流式 WAV 写入器。

    接受 float32 或 int16 的 numpy 数组，内部统一转为 int16 PCM 写入。
    float32 输入假定取值范围 [-1.0, 1.0]，超出会裁切。
    """

    def __init__(self, path: str | Path, sample_rate: int, channels: int) -> None:
        if sample_rate <= 0 or channels <= 0:
            raise ValueError(f"无效参数: sample_rate={sample_rate}, channels={channels}")
        self.path = Path(path)
        self.sample_rate = sample_rate
        self.channels = channels
        self._wave: wave.Wave_write | None = None

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._wave = wave.open(str(self.path), "wb")
        self._wave.setnchannels(self.channels)
        self._wave.setsampwidth(2)  # 16-bit
        self._wave.setframerate(self.sample_rate)

    def write(self, data: np.ndarray) -> None:
        """写入一块音频。data 形状为 (frames, channels)。"""
        if self._wave is None:
            raise RuntimeError("WavWriter 未打开，请先调用 open()")
        pcm = self._to_int16(data)
        self._wave.writeframes(pcm.tobytes())

    def close(self) -> None:
        if self._wave is not None:
            self._wave.close()
            self._wave = None
            logger.debug("WAV 已写入: %s", self.path)

    @staticmethod
    def _to_int16(data: np.ndarray) -> np.ndarray:
        if data.dtype == np.int16:
            return data
        if data.dtype in (np.float32, np.float64):
            clipped = np.clip(data, -1.0, 1.0)
            return (clipped * 32767.0).astype(np.int16)
        raise TypeError(f"不支持的音频 dtype: {data.dtype}")