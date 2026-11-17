"""滚动截图会话：滚动-截图-拼接循环，包含滚动有效性验证与鲁棒结束条件。"""
import threading
import time

import numpy as np

from app.core.capture.screen_capture import ScreenCapture
from app.core.models import Rect
from app.core.scrollshot.scroller import Scroller
from app.core.scrollshot.stitcher import MatchStrategy, Stitcher
from app.infra.logger import get_logger

logger = get_logger("scrollshot.session")

_STATIC_DIFF_THRESHOLD = 1.5
_STATIC_STREAK_TO_STOP = 3


class ScrollShotSession:
    def __init__(
        self,
        region: Rect,
        scroller: Scroller = None,
        stitcher: Stitcher = None,
        max_frames: int = 50,
        stable_threshold: float = 2.0,
        strategy=MatchStrategy.BALANCED,
    ) -> None:
        self.region = region
        self.scroller = scroller or Scroller()
        self.stitcher = stitcher or Stitcher(strategy=strategy)
        self.max_frames = max_frames
        self.stable_threshold = stable_threshold

        self._stop_event = threading.Event()
        self._thread = None
        self._result = None
        self._error = None
        self._frames = []
        self._scroll_positions = []
        self._progress_callback = None

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("滚动截图会话已在运行")
        self._stop_event.clear()
        self._result = None
        self._error = None
        self._frames = []
        self._scroll_positions = []
        self._thread = threading.Thread(
            target=self._run, name="scrollshot-session", daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def wait(self, timeout: float = 90.0):
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if self._error is not None:
            raise RuntimeError(f"滚动截图失败: {self._error}") from self._error
        return self._result

    def _run(self) -> None:
        try:
            self.scroller.scroll_to_top()
            static_streak = 0

            with ScreenCapture() as cap:
                for i in range(self.max_frames):
                    if self._stop_event.is_set():
                        break

                    frame = cap.grab(self.region)
                    self._frames.append(frame.image)
                    if self._progress_callback:
                        self._progress_callback(len(self._frames), f"已捕获 {len(self._frames)} 帧")

                    if len(self._frames) >= 2:
                        diff = self._mean_abs_diff(self._frames[-2], self._frames[-1])
                        if diff < _STATIC_DIFF_THRESHOLD:
                            static_streak += 1
                            logger.debug("第 %d 帧与上一帧几乎相同 (diff=%.2f)，streak=%d",
                                         len(self._frames), diff, static_streak)
                            if static_streak >= _STATIC_STREAK_TO_STOP:
                                logger.info("连续 %d 次滚动无新内容，判定已到底", static_streak)
                                break
                        else:
                            static_streak = 0

                    self.scroller.scroll_once()

            if len(self._frames) < 2:
                raise RuntimeError("只捕获到 1 帧，无法拼接。请确认目标窗口可滚动且鼠标位于窗口内。")

            if len(self._frames) <= 2:
                logger.warning(
                    "滚动截图仅捕获 %d 帧。如果这不是一个很短的页面，"
                    "滚动很可能未真正生效。请检查：\n"
                    "  1. 鼠标是否位于目标窗口内容区域\n"
                    "  2. 目标窗口是否已获得焦点\n"
                    "  3. 目标页面是否确实可滚动",
                    len(self._frames),
                )

            self._result = self.stitcher.stitch(self._frames)
            skipped = getattr(self.stitcher, "skipped_frames", 0)
            logger.info("滚动截图完成，共 %d 帧，拒绝 %d 帧", len(self._frames), skipped)
        except BaseException as exc:
            self._error = exc
            logger.exception("滚动截图会话异常退出")
        finally:
            self._stop_event.set()

    @staticmethod
    def _mean_abs_diff(a, b) -> float:
        if a.shape != b.shape:
            return 999.0
        return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))