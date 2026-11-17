"""多格式转码：MP4 → AVI / WMV。"""
from pathlib import Path

from app.core.export.ffmpeg_runner import FFmpegRunner
from app.infra.logger import get_logger

logger = get_logger("export.transcoder")

# 每种目标格式对应的视频/音频编码器
_FORMAT_CODECS = {
    "avi": {"v": "mpeg4", "a": "libmp3lame"},
    "wmv": {"v": "wmv2", "a": "wmav2"},
}


class Transcoder:
    def __init__(self, runner: FFmpegRunner = None):
        self._runner = runner or FFmpegRunner()

    def transcode(self, source: str | Path, target_format: str, output_dir: str | Path = None) -> Path:
        """把 source 转码为 target_format。返回输出文件路径。"""
        fmt = target_format.lower().lstrip(".")
        if fmt not in _FORMAT_CODECS:
            raise ValueError(f"不支持的目标格式: {fmt}，可选 {sorted(_FORMAT_CODECS)}")

        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"源文件不存在: {source}")

        if output_dir is None:
            output_path = source.with_suffix(f".{fmt}")
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{source.stem}.{fmt}"

        codecs = _FORMAT_CODECS[fmt]
        args = [
            "-y",
            "-i", str(source),
            "-c:v", codecs["v"],
            "-c:a", codecs["a"],
            str(output_path),
        ]
        logger.info("转码: %s → %s (%s)", source.name, output_path.name, fmt)
        self._runner.run(args)
        return output_path