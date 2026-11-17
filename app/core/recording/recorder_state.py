"""录制状态机：IDLE → PREPARING → RECORDING ↔ PAUSED → STOPPING → FINALIZING → IDLE。"""
import threading
from enum import Enum

from app.infra.logger import get_logger

logger = get_logger("recording.state")


class RecorderState(Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    RECORDING = "recording"
    PAUSED = "paused"          # 新增
    STOPPING = "stopping"
    FINALIZING = "finalizing"


_ALLOWED_TRANSITIONS = {
    RecorderState.IDLE: {RecorderState.PREPARING},
    RecorderState.PREPARING: {RecorderState.RECORDING, RecorderState.IDLE},
    RecorderState.RECORDING: {RecorderState.STOPPING, RecorderState.PAUSED},
    RecorderState.PAUSED: {RecorderState.RECORDING, RecorderState.STOPPING},
    RecorderState.STOPPING: {RecorderState.FINALIZING},
    RecorderState.FINALIZING: {RecorderState.IDLE},
}


class StateMachine:
    """线程安全的状态机。非法迁移直接抛异常，不静默忽略。"""

    def __init__(self) -> None:
        self._state = RecorderState.IDLE
        self._lock = threading.Lock()

    @property
    def state(self) -> RecorderState:
        with self._lock:
            return self._state

    def transition_to(self, target: RecorderState) -> None:
        with self._lock:
            allowed = _ALLOWED_TRANSITIONS[self._state]
            if target not in allowed:
                raise RuntimeError(f"非法状态迁移: {self._state.value} → {target.value}")
            logger.debug("状态迁移: %s → %s", self._state.value, target.value)
            self._state = target