"""滚动控制：win32api 直接发送 WM_MOUSEWHEEL，规避 pyautogui 在 Windows 上的已知缺陷。"""
import time

import win32api
import win32con

from app.infra.logger import get_logger

logger = get_logger("scrollshot.scroller")

WHEEL_DELTA = 120


class Scroller:
    """向鼠标当前所在窗口发送垂直滚动指令。

    step 与 pyautogui.scroll 语义一致：正数向上，负数向下。
    内部把"格数"换算为 WHEEL_DELTA 的倍数。
    """

    def __init__(self, step: int = -5, wait_after_scroll: float = 0.5) -> None:
        if step == 0:
            raise ValueError("滚动步长不能为 0")
        self.step = step
        self.wait_after_scroll = wait_after_scroll

    def scroll_once(self) -> None:
        # 坐标传 (0, 0)：鼠标位置不变，滚动发生在当前位置
        win32api.mouse_event(
            win32con.MOUSEEVENTF_WHEEL, 0, 0, self.step * WHEEL_DELTA, 0
        )
        time.sleep(self.wait_after_scroll)

    def scroll_to_top(self, times: int = 30, interval: float = 0.05) -> None:
        """向上滚动足够多次，尽量回到页面顶部。

        次数比之前更多，因为如果初始就不在顶部，需要更多次才能回顶。
        间隔缩短，避免回顶过程本身耗时过长。
        """
        for _ in range(times):
            win32api.mouse_event(
                win32con.MOUSEEVENTF_WHEEL, 0, 0, abs(self.step) * 3 * WHEEL_DELTA, 0
            )
            time.sleep(interval)
        time.sleep(0.4)  # 回顶后给页面一点渲染时间