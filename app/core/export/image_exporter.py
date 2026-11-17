"""图片导出：ndarray 编码为 PNG/JPG/BMP，支持质量参数。"""
from pathlib import Path

import numpy as np
from PIL import Image

from app.infra.logger import get_logger

logger = get_logger("export.image")

SUPPORTED_FORMATS = {"png", "jpg", "jpeg", "bmp"}


def _to_rgb(image: np.ndarray) -> np.ndarray:
    """BGRA / BGR / 灰度 → RGB 三通道。屏幕截图无透明度需求，统一丢弃 alpha。"""
    if image.ndim == 2:
        return np.stack([image] * 3, axis=-1)
    if image.ndim != 3:
        raise ValueError(f"不支持的图像维度: {image.ndim}")
    channels = image.shape[2]
    if channels == 4:      # BGRA
        return image[:, :, [2, 1, 0]]
    if channels == 3:      # BGR
        return image[:, :, ::-1]
    raise ValueError(f"不支持的通道数: {channels}")


class ImageExporter:
    """把捕获的 ndarray 保存为图片文件。"""

    @staticmethod
    def save(
        image: np.ndarray,
        path: str | Path,
        fmt: str | None = None,
        quality: int = 95,
    ) -> Path:
        """保存图片，返回最终写入的绝对路径。

        fmt 为 None 时从路径后缀推断，无后缀则默认 png。
        quality 仅对 jpg/jpeg 生效，取值范围 1-100。
        """
        path = Path(path)

        if fmt is None:
            fmt = path.suffix.lstrip(".").lower() or "png"
        else:
            fmt = fmt.lower().lstrip(".")
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(f"不支持的图片格式: {fmt}，可选 {sorted(SUPPORTED_FORMATS)}")

        # 路径无后缀时补齐，保证文件系统里能看出格式
        if not path.suffix:
            path = path.with_suffix(f".{'jpg' if fmt == 'jpeg' else fmt}")

        path.parent.mkdir(parents=True, exist_ok=True)
        rgb = _to_rgb(image)
        pil_image = Image.fromarray(rgb, mode="RGB")

        if fmt in ("jpg", "jpeg"):
            quality = max(1, min(100, int(quality)))
            pil_image.save(path, "JPEG", quality=quality)
        else:
            pil_image.save(path, fmt.upper())

        logger.info("图片已保存: %s (%s)", path, fmt)
        return path.resolve()