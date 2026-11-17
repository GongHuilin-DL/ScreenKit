"""应用启动入口：初始化日志、创建目录、加载配置、环境自检。"""
from app.infra.config import load_config
from app.infra.logger import init_logger
from app.infra.paths import PROJECT_ROOT, ensure_runtime_dirs, find_ffmpeg

BANNER = r"""
   _____                                 _    ___ _
  / ____|                               | |  |_ _| |
 | (___   ___ _ __ ___  ___ _ __   __ _  | | __| || |_
  \___ \ / __| '__/ _ \/ _ \ '_ \ / _` | | |/ /| || __|
  ____) | (__| | |  __/  __/ | | | (_| | |   < | || |_
 |_____/ \___|_|  \___|\___|_| |_|\__,_| |_|\_\___|\__|
"""


def run() -> int:
    """执行启动流程，返回进程退出码。"""
    logger = init_logger()
    logger.info("ScreenKit 启动中...")

    created = ensure_runtime_dirs()
    if created:
        logger.debug("已创建运行目录: %s", ", ".join(str(p) for p in created))

    config = load_config()
    app_meta = config.get("app", {})
    logger.info("配置加载完成: %s v%s", app_meta.get("name"), app_meta.get("version"))

    ffmpeg = find_ffmpeg()
    if ffmpeg:
        logger.info("检测到 ffmpeg: %s", ffmpeg)
    else:
        logger.warning("未找到 ffmpeg，音视频合成与转码功能将不可用（请放入 tools/ffmpeg/）")

    print(BANNER)
    print(f"项目根目录 : {PROJECT_ROOT}")
    print(
        "配置摘要   : "
        f"录制格式={config['recording']['video_format']}, "
        f"默认fps={config['capture']['default_fps']}, "
        f"系统声音={'开' if config['audio']['record_system'] else '关'}"
    )
    print("基础设施   : OK")
    logger.info("基础设施自检通过，等待接入 GUI（下一步：capture 模块）。")
    return 0