"""核心数据契约：Rect、FrameResult。"""
import time
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Rect:
    """屏幕矩形区域。

    坐标基于 Windows 虚拟桌面坐标系，x/y 允许为负
    （多显示器时左侧副屏的坐标是负数）。width/height 必须为正。
    """

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"Rect 宽高必须为正，收到 width={self.width}, height={self.height}"
            )

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def to_mss_region(self) -> dict[str, int]:
        """转换为 mss.grab() 接受的字典格式。"""
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}

    def contains(self, other: "Rect") -> bool:
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    @classmethod
    def from_ltrb(cls, left: int, top: int, right: int, bottom: int) -> "Rect":
        """由拖拽选区的起止点构造，自动规范化反向坐标。"""
        x = min(left, right)
        y = min(top, bottom)
        w = abs(right - left)
        h = abs(bottom - top)
        return cls(x=x, y=y, width=w, height=h)


@dataclass
class FrameResult:
    """一次抓帧的结果。image 为 BGRA 四通道 ndarray。"""

    image: np.ndarray
    timestamp: float
    region: Rect

    @classmethod
    def create(cls, image: np.ndarray, region: Rect) -> "FrameResult":
        return cls(image=image, timestamp=time.time(), region=region)