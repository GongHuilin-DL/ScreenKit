"""系统声音录制：基于 soundcard 的 WASAPI loopback 采集。"""
import threading
from pathlib import Path

import numpy as np

from app.core.audio.device_utils import SpeakerInfo, find_default_loopback_speaker
from app.core.audio.wav_writer import WavWriter
from app.infra.logger import get_logger

logger = get_logger("audio.system")


class SystemAudioRecorder:
    def __init__(self, speaker: SpeakerInfo | None = None) -> None:
        self._speaker = speaker
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event() # 新增
        self._writer: WavWriter | None = None
        self._error: BaseException | None = None
        self._sample_rate = 48000
        self._channels = 2

    def start(self, output_path: str | Path, sample_rate: int = 48000, channels: int = 2, block_frames: int = 4800) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("系统声音录制已在运行")

        speaker = self._speaker or find_default_loopback_speaker()
        if speaker is None:
            raise RuntimeError("未找到可用的 loopback 输出设备。请确认 soundcard 已安装且系统有播放设备。")

        self._sample_rate = sample_rate
        self._channels = channels
        self._stop_event.clear()
        self._pause_event.clear()
        self._error = None
        self._writer = WavWriter(output_path, sample_rate, channels)

        self._thread = threading.Thread(
            target=self._run,
            args=(speaker, block_frames),
            name="system-audio",
            daemon=True,
        )
        self._thread.start()
        logger.info("系统声音录制已启动: %s (%s)", output_path, speaker.name)

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("系统声音线程未在 %.1fs 内退出", timeout)
        self._thread = None
        if self._error is not None:
            raise RuntimeError(f"系统声音录制失败: {self._error}") from self._error

    def _run(self, speaker: SpeakerInfo, block_frames: int) -> None:
        try:
            import soundcard as sc

            mic = sc.get_microphone(id=speaker.id, include_loopback=True)
            if mic is None:
                raise RuntimeError(f"无法获取 loopback 麦克风: {speaker.name}")

            self._writer.open()
            with mic.recorder(
                samplerate=self._sample_rate,
                channels=self._channels,
                blocksize=block_frames,
            ) as recorder:
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=block_frames)
                    # 暂停时丢弃数据
                    if not self._pause_event.is_set() and data is not None and len(data) > 0:
                        self._writer.write(np.asarray(data))
        except BaseException as exc:
            self._error = exc
            logger.exception("系统声音采集线程异常退出")
            self._stop_event.set()
        finally:
            if self._writer is not None:
                self._writer.close()