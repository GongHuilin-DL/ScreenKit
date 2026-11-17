"""跨线程事件定义与事件总线。"""
import queue
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    STATE_CHANGED = "state_changed"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_FAILED = "recording_failed"
    SCREENSHOT_SAVED = "screenshot_saved"
    INFO = "info"
    ERROR = "error"


@dataclass
class Event:
    type: EventType
    message: str = ""
    payload: dict = field(default_factory=dict)


class EventBus:
    """线程安全的事件总线。工作线程 post，UI 线程 poll。"""

    def __init__(self):
        self._queue = queue.Queue()

    def post(self, event):
        self._queue.put(event)

    def poll(self, max_items=50):
        """一次性取出当前队列中的所有事件（最多 max_items 个）。"""
        events = []
        for _ in range(max_items):
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events