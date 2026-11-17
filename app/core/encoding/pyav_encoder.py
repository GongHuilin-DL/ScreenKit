"""PyAV 编码器：容器与流管理、逐帧编码、PTS 控制、flush。"""
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from app.core.encoding.encoder_config import EncoderConfig
from app.infra.logger import get_logger

logger = get_logger("encoding.pyav")


def _to_bgr24(image: np.ndarray) -> np.ndarray:
    """BGRA（mss 输出）→ BGR24（PyAV 接受的 bgr24）。alpha 直接丢弃。"""
    if image.ndim != 3:
        raise ValueError(f"期望三维图像，收到 shape={image.shape}")
    if image.shape[2] == 4:
        return np.ascontiguousarray(image[:, :, :3])
    if image.shape[2] == 3:
        return np.ascontiguousarray(image)
    raise ValueError(f"不支持的通道数: {image.shape[2]}")


class PyAvEncoder:
    """封装一个输出容器与视频流。

    用法：
        enc = PyAvEncoder(path, config)
        enc.open()
        enc.write(frame_index, image)   # frame_index 从 0 开始递增
        enc.close()                     # 内部负责 flush

    线程约束：PyAvEncoder 不是线程安全的，只能在一个线程内使用。
    """

    def __init__(self, output_path: str | Path, config: EncoderConfig) -> None:
        self.output_path = Path(output_path)
        self.config = config
        self._container: av.container.OutputContainer | None = None
        self._stream = None
        self._frames_written = 0

    def open(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._container = av.open(str(self.output_path), mode="w")
        self._stream = self._container.add_stream(self.config.codec, rate=self.config.fps)
        self._stream.width = self.config.width
        self._stream.height = self.config.height
        self._stream.pix_fmt = self.config.pix_fmt
        self._stream.options = self.config.codec_options()
        # time_base = 1/fps，这样 pts 就是帧序号，不需要做浮点换算
        self._stream.codec_context.time_base = Fraction(1, self.config.fps)
        logger.info(
            "编码器已打开: %s codec=%s %dx%d@%dfps",
            self.output_path, self.config.codec,
            self.config.width, self.config.height, self.config.fps,
        )

    def write(self, frame_index: int, image: np.ndarray) -> None:
        """编码一帧。frame_index 是理想采集序号，直接作为 pts。"""
        if self._container is None or self._stream is None:
            raise RuntimeError("编码器未打开，请先调用 open()")

        bgr = _to_bgr24(image)
        if bgr.shape[:2] != (self.config.height, self.config.width):
            raise ValueError(
                f"帧尺寸 {bgr.shape[1]}x{bgr.shape[0]} 与编码配置 "
                f"{self.config.width}x{self.config.height} 不一致"
            )

        av_frame = av.VideoFrame.from_ndarray(bgr, format="bgr24")
        av_frame.pts = frame_index
        av_frame.time_base = self._stream.codec_context.time_base

        for packet in self._stream.encode(av_frame):
            self._container.mux(packet)
        self._frames_written += 1

    def close(self) -> None:
        """flush 编码器并关闭容器。可重复调用。"""
        if self._container is None:
            return
        try:
            if self._stream is not None:
                for packet in self._stream.encode():
                    self._container.mux(packet)
        except Exception:
            logger.exception("编码器 flush 时发生异常，视频文件可能不完整")
        finally:
            self._container.close()
            self._container = None
            self._stream = None
        logger.info("编码器已关闭: %s，共写入 %d 帧", self.output_path, self._frames_written)

    @property
    def frames_written(self) -> int:
        return self._frames_written