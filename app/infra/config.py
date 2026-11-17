"""配置加载：内置默认值 + config/default.yaml 深度合并。"""
import copy
import logging
from pathlib import Path
from typing import Any

from app.infra.default_config import DEFAULT_CONFIG
from app.infra.paths import CONFIG_DIR

logger = logging.getLogger("screenkit.config")

DEFAULT_CONFIG_FILE = CONFIG_DIR / "default.yaml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """递归合并字典，override 中的标量值覆盖 base，字典继续下钻。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """加载配置。任何异常都降级为内置默认配置，不阻塞启动。"""
    config = copy.deepcopy(DEFAULT_CONFIG)
    path = Path(config_path) if config_path else DEFAULT_CONFIG_FILE

    if not path.is_file():
        logger.warning("配置文件不存在，使用内置默认配置: %s", path)
        return config

    try:
        import yaml  # 延迟导入，未安装时不影响启动
    except ImportError:
        logger.warning("未安装 PyYAML，跳过 %s，使用内置默认配置", path)
        return config

    try:
        with path.open("r", encoding="utf-8") as fp:
            user_config = yaml.safe_load(fp) or {}
    except Exception as exc:  # yaml 语法错误、编码错误等
        logger.error("读取配置文件失败，使用内置默认配置: %s", exc)
        return config

    if not isinstance(user_config, dict):
        logger.warning("配置文件内容不是映射结构，忽略: %s", path)
        return config

    merged = _deep_merge(config, user_config)
    logger.info("已加载配置文件: %s", path)
    return merged