"""编码参数容器：codec、fps、宽高、crf、pix_fmt 及校验。"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EncoderConfig:
    """一段视频的编码参数。frozen 保证录制过程中参数不被意外修改。"""

    width: int
    height: int
    fps: int = 30
    codec: str = "libx264"
    pix_fmt: str = "yuv420p"
    crf: int = 23
    preset: str = "fast"
    options: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"编码宽高必须为正，收到 {self.width}x{self.height}")
        if self.fps <= 0:
            raise ValueError(f"fps 必须为正，收到 {self.fps}")
        if not 0 <= self.crf <= 51:
            raise ValueError(f"crf 应在 0-51 之间，收到 {self.crf}")
        # H.264 要求宽高为偶数（yuv420p 的色度下采样以 2x2 为单位）
        if self.width % 2 or self.height % 2:
            raise ValueError(
                f"H.264/yuv420p 要求宽高为偶数，收到 {self.width}x{self.height}。"
                "请用 Rect 裁剪或请求偶数尺寸。"
            )

    def codec_options(self) -> dict[str, str]:
        """合并用户自定义 options 与默认 crf/preset。"""
        opts = {"crf": str(self.crf), "preset": self.preset}
        opts.update(self.options)
        return opts