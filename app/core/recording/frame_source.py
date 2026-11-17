"""帧源：按目标 fps 节拍循环抓帧，产出带序号与时间戳的帧（含鼠标特效）。"""
import time
from dataclasses import dataclass

import numpy as np

from app.core.capture.screen_capture import ScreenCapture
from app.core.models import Rect
from app.infra.logger import get_logger

logger = get_logger("recording.frame_source")

try:
    import cv2
    import win32api
    _HAS_CV2 = True
except ImportError:
    cv2 = None
    win32api = None
    _HAS_CV2 = False

try:
    from pynput import mouse
    _HAS_PYNPUT = True
except ImportError:
    _HAS_PYNPUT = False


@dataclass
class CapturedFrame:
    index: int
    image: np.ndarray
    scheduled_time: float
    actual_time: float


class FrameSource:
    """按固定节拍产帧的生成器。"""

    def __init__(self, region: Rect, fps: int, highlight_mouse: bool = True) -> None:
        if fps <= 0:
            raise ValueError(f"fps 必须为正，收到 {fps}")
        self.region = region
        self.fps = fps
        self.highlight_mouse = highlight_mouse and _HAS_CV2
        self._capture: ScreenCapture | None = None
        self._mouse_listener = None
        self._click_time = 0.0

    def open(self) -> None:
        self._capture = ScreenCapture()
        self._capture.open()
        
        if self.highlight_mouse and _HAS_PYNPUT:
            def on_click(x, y, button, pressed):
                if button == mouse.Button.left and pressed:
                    self._click_time = time.perf_counter()
            self._mouse_listener = mouse.Listener(on_click=on_click)
            self._mouse_listener.start()

    def close(self) -> None:
        if self._capture is not None:
            self._capture.close()
            self._capture = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None

    def stream(self, stop_event, pause_event):
        if self._capture is None:
            self.open()
        assert self._capture is not None

        interval = 1.0 / self.fps
        next_time = time.perf_counter()
        index = 0

        while not stop_event.is_set():
            # 暂停处理逻辑
            if pause_event.is_set():
                time.sleep(0.05)
                next_time = time.perf_counter() # 恢复时以当前时间为基准，避免疯狂追帧
                continue

            now = time.perf_counter()
            if now < next_time:
                time.sleep(next_time - now)

            actual = time.perf_counter()
            frame = self._capture.grab(self.region)
            
            # 图像后处理（画鼠标特效）
            image = frame.image
            if self.highlight_mouse:
                image = self._draw_mouse_effects(image)

            yield CapturedFrame(
                index=index,
                image=image,
                scheduled_time=next_time,
                actual_time=actual,
            )
            index += 1
            next_time += interval

    def _draw_mouse_effects(self, image: np.ndarray) -> np.ndarray:
        img_bgr = image[:, :, :3].copy() if image.ndim == 3 and image.shape[2] == 4 else image.copy()
        
        try:
            cx, cy = win32api.GetCursorPos()
            rx = cx - self.region.x
            ry = cy - self.region.y
            
            h, w = img_bgr.shape[:2]
            if 0 <= rx < w and 0 <= ry < h:
                cv2.circle(img_bgr, (rx, ry), 16, (0, 255, 255), 2)
                elapsed = time.perf_counter() - self._click_time
                if elapsed < 0.6:
                    radius = int(16 + elapsed * 100)
                    alpha = max(0.0, 1.0 - elapsed / 0.6)
                    
                    overlay = img_bgr.copy()
                    cv2.circle(overlay, (rx, ry), radius, (0, 0, 255), 2)
                    cv2.addWeighted(overlay, alpha, img_bgr, 1 - alpha, 0, img_bgr)
        except Exception:
            pass
            
        return img_bgr