"""路径管理：项目根定位、运行目录创建、ffmpeg 可执行文件查找。

同时支持开发环境（python main.py）和 PyInstaller 打包环境（ScreenKit.exe）。
"""
import shutil
import sys
from pathlib import Path

APP_NAME = "ScreenKit"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包后的环境中。"""
    return getattr(sys, "frozen", False)


def resource_path(relative: str) -> Path:
    """获取打包资源的绝对路径。

    打包后资源在 sys._MEIPASS 下（onedir 模式为 _internal 目录）；
    开发环境下基于项目根目录。
    """
    if is_frozen():
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]
    return base / relative


# 开发环境：项目根目录；打包环境：exe 所在目录（用于可写的运行目录）
if is_frozen():
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parents[2]

CONFIG_DIR = APP_DIR / "config"
OUTPUT_DIR = APP_DIR / "output"
TEMP_DIR = APP_DIR / "temp"
LOG_DIR = APP_DIR / "logs"

_REQUIRED_DIRS = (OUTPUT_DIR, TEMP_DIR, LOG_DIR)


def ensure_runtime_dirs() -> list[Path]:
    created = []
    for directory in _REQUIRED_DIRS:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
    return created


def resolve_dir(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = APP_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_ffmpeg() -> str | None:
    """按优先级查找 ffmpeg：
    1. 打包环境：sys._MEIPASS/ffmpeg/ffmpeg.exe
    2. 开发环境：tools/ffmpeg/ffmpeg.exe
    3. 系统 PATH 中的 ffmpeg
    """
    bundled = resource_path("ffmpeg/ffmpeg.exe")
    if bundled.is_file():
        return str(bundled)
    if not is_frozen():
        dev_bundled = APP_DIR / "tools" / "ffmpeg" / "ffmpeg.exe"
        if dev_bundled.is_file():
            return str(dev_bundled)
    return shutil.which("ffmpeg")