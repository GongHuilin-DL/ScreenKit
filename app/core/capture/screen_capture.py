"""截屏捕获：封装 mss，支持显示器枚举、全屏与区域单帧抓取。"""
import numpy as np
import mss

from app.core.models import FrameResult, Rect
from app.infra.logger import get_logger

logger = get_logger("capture.screen")


class ScreenCapture:
    """基于 mss 的屏幕捕获器。

    线程约束：mss 的实例持有 Windows GDI 句柄，不能跨线程共享。
    每个线程必须创建自己的 ScreenCapture 实例。推荐用 with 语句：
        with ScreenCapture() as cap:
            frame = cap.grab(region)
    """

    def __init__(self) -> None:
        self._sct = None

    def __enter__(self) -> "ScreenCapture":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.close()

    def open(self) -> None:
        if self._sct is None:
            self._sct = mss.mss()
            logger.debug("mss 实例已初始化")

    def close(self) -> None:
        if self._sct is not None:
            self._sct.close()
            self._sct = None
            logger.debug("mss 实例已释放")

    def list_monitors(self) -> list[dict[str, int]]:
        """返回显示器列表。索引 0 为虚拟桌面合并区域，1..n 为单个显示器。"""
        self.open()
        return list(self._sct.monitors)

    def primary_monitor_rect(self) -> Rect:
        """主显示器的矩形。mss 的 monitors[1] 是主显示器。"""
        self.open()
        monitors = self._sct.monitors
        if len(monitors) < 2:
            raise RuntimeError("未检测到任何显示器")
        m = monitors[1]
        return Rect(x=m["left"], y=m["top"], width=m["width"], height=m["height"])

    def virtual_screen_rect(self) -> Rect:
        """所有显示器合并后的虚拟桌面矩形。"""
        self.open()
        m = self._sct.monitors[0]
        return Rect(x=m["left"], y=m["top"], width=m["width"], height=m["height"])

    def grab(self, region: Rect | None = None) -> FrameResult:
        """抓取一帧。region 为 None 时抓主显示器全屏。"""
        self.open()

        if region is None:
            region = self.primary_monitor_rect()
        if not isinstance(region, Rect):
            raise TypeError(f"region 必须是 Rect 或 None，收到 {type(region).__name__}")

        shot = self._sct.grab(region.to_mss_region())
        image = np.array(shot)  # shape (h, w, 4)，通道顺序 BGRA
        logger.debug("抓帧完成 region=%s shape=%s", region, image.shape)
        return FrameResult.create(image=image, region=region)