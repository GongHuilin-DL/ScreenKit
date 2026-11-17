"""滚动截图用例：驱动会话并把结果导出为长图。"""
from datetime import datetime
from pathlib import Path

from app.core.export.image_exporter import ImageExporter
from app.core.models import Rect
from app.core.scrollshot.scroller import Scroller
from app.core.scrollshot.session import ScrollShotSession
from app.core.scrollshot.stitcher import MatchStrategy, Stitcher
from app.infra.logger import get_logger

logger = get_logger("controller.scrollshot")


class ScrollShotController:
    def __init__(self, output_dir, quality: int = 95):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quality = quality
        self._session = None

    @property
    def is_running(self):
        return (
            self._session is not None
            and self._session._thread is not None
            and self._session._thread.is_alive()
        )

    def start(self, region: Rect, step: int = -5, wait: float = 0.5,
              progress_callback=None, strategy: MatchStrategy = MatchStrategy.BALANCED):
        if self.is_running:
            raise RuntimeError("滚动截图已在运行")
        scroller = Scroller(step=step, wait_after_scroll=wait)
        stitcher = Stitcher(strategy=strategy)
        self._session = ScrollShotSession(
            region, scroller=scroller, stitcher=stitcher, strategy=strategy,
        )
        if progress_callback:
            self._session.set_progress_callback(progress_callback)
        self._session.start()

    def stop(self):
        if self._session is not None:
            self._session.stop()

    def wait_and_save(self, fmt: str = "png") -> Path:
        if self._session is None:
            raise RuntimeError("没有正在进行的滚动截图会话")
        image = self._session.wait()
        self._session = None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"scrollshot_{timestamp}.{fmt}"
        import numpy as np
        arr = np.array(image.convert("RGB"))[:, :, ::-1]
        return ImageExporter.save(arr, path, fmt=fmt, quality=self.quality)