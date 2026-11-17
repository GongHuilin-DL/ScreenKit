"""音视频合成：单音频 mux 与双音频 amix 混合。"""
from pathlib import Path

from app.core.export.ffmpeg_runner import FFmpegRunner
from app.infra.logger import get_logger

logger = get_logger("export.muxer")


class Muxer:
    """把无声视频与一到两个 WAV 合成为带声音的 MP4。

    - 单个音频：-c:v copy -c:a aac -shortest
    - 两个音频：先用 amix 混合为单轨，再与视频 mux。
      使用 normalize=0 避免 amix 默认把每个输入减半。
    """

    def __init__(self, runner: FFmpegRunner | None = None) -> None:
        self._runner = runner or FFmpegRunner()

    def mux_single(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
        audio_bitrate: str = "192k",
    ) -> Path:
        """视频流直接 copy，音频转 AAC，按时长较短者截断。"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._runner.run(
            [
                "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", audio_bitrate,
                "-shortest",
                str(output_path),
            ]
        )
        logger.info("合成完成: %s", output_path)
        return output_path

    def mux_mixed(
        self,
        video_path: str | Path,
        audio_a: str | Path,
        audio_b: str | Path,
        output_path: str | Path,
        weight_a: float = 1.0,
        weight_b: float = 1.0,
        audio_bitrate: str = "192k",
    ) -> Path:
        """两路音频先 amix 混合，再与视频 mux。weight 控制各路音量比例。"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        filter_complex = (
            f"[1:a]volume={weight_a}[a1];"
            f"[2:a]volume={weight_b}[a2];"
            f"[a1][a2]amix=inputs=2:duration=longest:normalize=0[aout]"
        )
        self._runner.run(
            [
                "-y",
                "-i", str(video_path),
                "-i", str(audio_a),
                "-i", str(audio_b),
                "-filter_complex", filter_complex,
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", audio_bitrate,
                "-shortest",
                str(output_path),
            ]
        )
        logger.info("混合合成完成: %s", output_path)
        return output_path