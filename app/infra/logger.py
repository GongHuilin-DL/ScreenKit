"""日志配置：控制台 + logs/app.log 滚动文件双输出。"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.infra.paths import LOG_DIR

_LOGGER_NAME = "screenkit"
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _force_utf8_streams() -> None:
    """让标准输出使用 UTF-8，规避 Windows GBK 控制台的中文乱码问题。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def init_logger(level: int = logging.DEBUG, log_dir: str | Path | None = None) -> logging.Logger:
    """初始化根 logger。可重复调用，每次都会重建 handler。"""
    _force_utf8_streams()

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # 清理旧 handler，防止重复初始化时同一条日志被打印多次
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    target_dir = Path(log_dir) if log_dir else LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        target_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # 文件里始终记录最详细的信息
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """获取带层级的子 logger，例如 get_logger("capture")。"""
    base = logging.getLogger(_LOGGER_NAME)
    return base if not name else base.getChild(name)