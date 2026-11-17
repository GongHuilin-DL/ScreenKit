"""麦克风录制：基于 sounddevice 的输入流采集。"""
import threading
from pathlib import Path

import numpy as np

from app.core.audio.wav_writer import WavWriter
from app.infra.logger import get_logger

logger = get_logger("audio.mic")


class MicrophoneRecorder:
    def __init__(self, device_index: int | None = None) -> None:
        self._device_index = device_index
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event() # 新增
        self._writer: WavWriter | None = None
        self._error: BaseException | None = None
        self._sample_rate = 48000
        self._channels = 1

    def start(self, output_path: str | Path, sample_rate: int = 48000, channels: int = 1, block_frames: int = 4800) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("麦克风录制已在运行")

        self._sample_rate = sample_rate
        self._channels = channels
        self._stop_event.clear()
        self._pause_event.clear()
        self._error = None
        self._writer = WavWriter(output_path, sample_rate, channels)

        self._thread = threading.Thread(
            target=self._run,
            args=(block_frames,),
            name="microphone",
            daemon=True,
        )
        self._thread.start()
        logger.info("麦克风录制已启动: %s", output_path)

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("麦克风线程未在 %.1fs 内退出", timeout)
        self._thread = None
        if self._error is not None:
            raise RuntimeError(f"麦克风录制失败: {self._error}") from self._error

    def _run(self, block_frames: int) -> None:
        try:
            import sounddevice as sd

            self._writer.open()
            with sd.InputStream(
                device=self._device_index,
                samplerate=self._sample_rate,
                channels=self._channels,
                blocksize=block_frames,
                dtype="float32",
            ) as stream:
                while not self._stop_event.is_set():
                    data, overflowed = stream.read(block_frames)
                    if overflowed:
                        logger.warning("麦克风缓冲区溢出，部分音频可能丢失")
                    # 暂停时丢弃数据
                    if not self._pause_event.is_set() and data is not None and len(data) > 0:
                        self._writer.write(np.asarray(data))
        except BaseException as exc:
            self._error = exc
            logger.exception("麦克风采集线程异常退出")
            self._stop_event.set()
        finally:
            if self._writer is not None:
                self._writer.close()