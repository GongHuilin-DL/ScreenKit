"""录制器：捕获线程 → 有界队列 → 编码线程，双线程背压。"""
import queue
import threading
from pathlib import Path

from app.core.encoding.encoder_config import EncoderConfig
from app.core.encoding.pyav_encoder import PyAvEncoder
from app.core.models import Rect
from app.core.recording.frame_source import FrameSource
from app.core.recording.recorder_state import RecorderState, StateMachine
from app.infra.logger import get_logger

logger = get_logger("recording.recorder")

_QUEUE_MAXSIZE = 8
_STOP_SENTINEL = object()


class Recorder:
    def __init__(self, region: Rect, output_path: str | Path, config: EncoderConfig, highlight_mouse: bool = True) -> None:
        self.region = region
        self.output_path = Path(output_path)
        self.config = config
        self.highlight_mouse = highlight_mouse

        self._state = StateMachine()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._frame_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._capture_thread: threading.Thread | None = None
        self._encode_thread: threading.Thread | None = None
        self._last_error: BaseException | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> RecorderState:
        return self._state.state

    @property
    def last_error(self) -> BaseException | None:
        with self._lock:
            return self._last_error

    def start(self) -> None:
        self._state.transition_to(RecorderState.PREPARING)

        probe = PyAvEncoder(self.output_path, self.config)
        try:
            probe.open()
        finally:
            probe.close()

        self._stop_event.clear()
        self._pause_event.clear()
        self._last_error = None
        self._state.transition_to(RecorderState.RECORDING)

        self._encode_thread = threading.Thread(
            target=self._encode_loop, name="encode-worker", daemon=True
        )
        self._capture_thread = threading.Thread(
            target=self._capture_loop, name="capture-worker", daemon=True
        )
        self._encode_thread.start()
        self._capture_thread.start()
        logger.info("录制已启动: %s", self.output_path)

    def pause(self) -> None:
        if self._state.state != RecorderState.RECORDING:
            raise RuntimeError(f"当前状态不可暂停: {self._state.state.value}")
        self._pause_event.set()
        self._state.transition_to(RecorderState.PAUSED)
        logger.info("录制已暂停")

    def resume(self) -> None:
        if self._state.state != RecorderState.PAUSED:
            raise RuntimeError(f"当前状态不可恢复: {self._state.state.value}")
        self._pause_event.clear()
        self._state.transition_to(RecorderState.RECORDING)
        logger.info("录制已恢复")

    def stop(self, timeout: float = 10.0) -> Path:
        if self._state.state not in (RecorderState.RECORDING, RecorderState.PAUSED):
            raise RuntimeError(f"当前状态不可停止: {self._state.state.value}")

        self._state.transition_to(RecorderState.STOPPING)
        self._stop_event.set()

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=timeout)
        if self._encode_thread is not None:
            self._encode_thread.join(timeout=timeout)

        self._state.transition_to(RecorderState.FINALIZING)
        self._state.transition_to(RecorderState.IDLE)

        error = self.last_error
        if error is not None:
            raise RuntimeError(f"录制过程中发生错误: {error}") from error
        logger.info("录制已停止: %s", self.output_path)
        return self.output_path

    def _capture_loop(self) -> None:
        source = FrameSource(self.region, self.config.fps, self.highlight_mouse)
        try:
            source.open()
            for frame in source.stream(self._stop_event, self._pause_event):
                self._put_frame(frame)
        except BaseException as exc:
            self._record_error(exc)
            logger.exception("捕获线程异常退出")
        finally:
            source.close()
            self._put_frame(_STOP_SENTINEL)

    def _put_frame(self, item) -> None:
        while True:
            try:
                self._frame_queue.put(item, timeout=0.2)
                return
            except queue.Full:
                if self._stop_event.is_set():
                    return

    def _encode_loop(self) -> None:
        encoder = PyAvEncoder(self.output_path, self.config)
        try:
            encoder.open()
            while True:
                item = self._frame_queue.get()
                if item is _STOP_SENTINEL:
                    break
                encoder.write(item.index, item.image)
                self._frame_queue.task_done()
        except BaseException as exc:
            self._record_error(exc)
            logger.exception("编码线程异常退出")
        finally:
            encoder.close()

    def _record_error(self, exc: BaseException) -> None:
        with self._lock:
            if self._last_error is None:
                self._last_error = exc
        self._stop_event.set()