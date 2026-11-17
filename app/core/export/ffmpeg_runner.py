"""FFmpeg 可执行文件定位与命令执行封装。"""
import shutil
import subprocess
from pathlib import Path

from app.infra.logger import get_logger
from app.infra.paths import find_ffmpeg

logger = get_logger("export.ffmpeg")


class FFmpegError(RuntimeError):
    """FFmpeg 执行失败，携带 stderr 尾部用于排查。"""

    def __init__(self, message: str, stderr_tail: str = "") -> None:
        super().__init__(message)
        self.stderr_tail = stderr_tail


class FFmpegRunner:
    """执行 FFmpeg 命令，捕获 stderr，统一错误处理。

    构造时即校验可执行文件可用性：
        - 传入路径：按路径或 PATH 命令名解析，找不到立即抛 FFmpegError
        - 不传：用 find_ffmpeg() 自动查找，找不到立即抛 FFmpegError
    """

    def __init__(self, executable: str | None = None) -> None:
        if executable is not None:
            # 支持绝对路径、相对路径、以及裸命令名（从 PATH 查找）
            resolved = executable if Path(executable).is_file() else shutil.which(executable)
            if not resolved:
                raise FFmpegError(f"FFmpeg 可执行文件不存在或不可执行: {executable}")
            self._executable = str(resolved)
        else:
            found = find_ffmpeg()
            if not found:
                raise FFmpegError(
                    "未找到 ffmpeg。请将 ffmpeg.exe 放入 tools/ffmpeg/ 或加入系统 PATH。"
                )
            self._executable = found

    def run(self, args, timeout=300.0):
        """执行 ffmpeg 命令。args 不包含可执行文件本身。"""
        cmd = [self._executable, "-hide_banner", "-loglevel", "error"] + args
        logger.debug("FFmpeg 命令: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise FFmpegError(f"FFmpeg 执行超时（{timeout}s）")
        except FileNotFoundError:
            raise FFmpegError(f"FFmpeg 可执行文件不可用: {self._executable}")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            tail = "\n".join(stderr.splitlines()[-8:])
            logger.error("FFmpeg 失败 (returncode=%d):\n%s", result.returncode, tail)
            raise FFmpegError(
                f"FFmpeg 返回码 {result.returncode}", stderr_tail=tail
            )
        return result