"""用户偏好配置：负责 user.yaml 的读写。"""
import copy
import logging
from pathlib import Path
from typing import Any

from app.infra.paths import CONFIG_DIR

logger = logging.getLogger("screenkit.user_config")
USER_CONFIG_FILE = CONFIG_DIR / "user.yaml"

# 默认用户偏好
DEFAULT_USER_PREFS = {
    "output_dir": "output",
    "image_format": "png",
    "video_format": "mp4",
    "fps": "30",
    "scroll_step": "-5",
    "scroll_wait": "0.5",
    "record_system_audio": True,
    "record_microphone": False,
}

def load_user_config() -> dict[str, Any]:
    """加载用户配置，如果不存在则返回默认配置。"""
    config = copy.deepcopy(DEFAULT_USER_PREFS)
    if not USER_CONFIG_FILE.is_file():
        return config

    try:
        import yaml
        with USER_CONFIG_FILE.open("r", encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}
            if isinstance(user_data, dict):
                config.update(user_data)
    except Exception as e:
        logger.warning("读取用户配置失败，使用默认配置: %s", e)
    return config

def save_user_config(prefs: dict[str, Any]) -> None:
    """保存用户配置到 user.yaml。"""
    try:
        import yaml
        # 过滤掉不需要保存的键（如果有的话）
        save_data = {k: v for k, v in prefs.items() if k in DEFAULT_USER_PREFS}
        with USER_CONFIG_FILE.open("w", encoding="utf-8") as f:
            yaml.safe_dump(save_data, f, allow_unicode=True, default_flow_style=False)
        logger.info("用户配置已保存: %s", USER_CONFIG_FILE)
    except Exception as e:
        logger.error("保存用户配置失败: %s", e)