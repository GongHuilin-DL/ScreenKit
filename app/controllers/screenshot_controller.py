"""截图用例：全屏或区域截图，并调用图片导出。"""
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.core.capture.screen_capture import ScreenCapture
from app.core.export.image_exporter import ImageExporter, _to_rgb
from app.core.models import FrameResult, Rect
from app.infra.logger import get_logger

logger = get_logger("controller.screenshot")


class ScreenshotController:
    """编排"抓帧 → 导出"这一用例。

    依赖两个能力：ScreenCapture（抓帧）和 ImageExporter（编码保存）。
    自身只负责文件名生成和目录管理，不含捕获或编码细节。
    """

    def __init__(self, output_dir: str | Path, quality: int = 95) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quality = quality

    # --- 供快速标注使用的新接口（返回 PIL Image 对象，不落盘） ---

    def capture_full_screen_image(self) -> Image.Image:
        """截取全屏并返回 PIL Image 对象，不自动保存。"""
        with ScreenCapture() as cap:
            frame = cap.grab(cap.primary_monitor_rect())
        rgb = _to_rgb(frame.image)
        return Image.fromarray(rgb)

    def capture_region_image(self, region: Rect) -> Image.Image:
        """截取指定区域并返回 PIL Image 对象，不自动保存。"""
        if not isinstance(region, Rect):
            raise TypeError(f"region 必须是 Rect，收到 {type(region).__name__}")
        with ScreenCapture() as cap:
            frame = cap.grab(region)
        rgb = _to_rgb(frame.image)
        return Image.fromarray(rgb)

    # --- 原有的自动保存接口保持不变 ---

    def capture_full_screen(self, fmt: str = "png") -> Path:
        with ScreenCapture() as cap:
            frame = cap.grab(cap.primary_monitor_rect())
        return self._save(frame, fmt)

    def capture_virtual_screen(self, fmt: str = "png") -> Path:
        """跨多显示器的整块虚拟桌面。"""
        with ScreenCapture() as cap:
            frame = cap.grab(cap.virtual_screen_rect())
        return self._save(frame, fmt)

    def capture_region(self, region: Rect, fmt: str = "png") -> Path:
        if not isinstance(region, Rect):
            raise TypeError(f"region 必须是 Rect，收到 {type(region).__name__}")
        with ScreenCapture() as cap:
            frame = cap.grab(region)
        return self._save(frame, fmt)

    def _save(self, frame: FrameResult, fmt: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"screenshot_{timestamp}.{fmt}"
        return ImageExporter.save(
            frame.image,
            self.output_dir / filename,
            fmt=fmt,
            quality=self.quality,
        )