"""应用启动入口：初始化日志、配置、自检，启动 GUI。"""
import ctypes
import tkinter as tk
from tkinter import ttk

from app.infra.config import load_config
from app.infra.logger import init_logger
from app.infra.paths import ensure_runtime_dirs, find_ffmpeg, resource_path

try:
    from app.infra.first_run_check import run_first_run_check, show_check_dialog_if_needed
    _HAS_CHECK = True
except ImportError:
    _HAS_CHECK = False


def _enable_high_dpi():
    """开启 Windows 高 DPI 感知，解决界面模糊和截图坐标偏移。"""
    try:
        # 2 表示 PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _apply_theme(root):
    """应用 sv-ttk 深色主题并适配 DPI 缩放。"""
    # 动态适配 DPI 缩放，防止界面过大或过小
    scale = root.winfo_fpixels('1i') / 72.0
    root.tk.call('tk', 'scaling', scale)

    try:
        import sv_ttk
        sv_ttk.set_theme("dark")
    except ImportError:
        pass

    style = ttk.Style(root)
    style.configure(".", font=("Microsoft YaHei UI", 11))
    style.configure("TLabel", font=("Microsoft YaHei UI", 11))
    style.configure("TButton", padding=(14, 8), font=("Microsoft YaHei UI", 11))
    style.configure("Accent.TButton", padding=(16, 14), font=("Microsoft YaHei UI", 14, "bold"))
    style.configure("Secondary.TButton", padding=(14, 12), font=("Microsoft YaHei UI", 12))
    style.configure("TCheckbutton", font=("Microsoft YaHei UI", 11))
    style.configure("TLabelframe", padding=6)
    style.configure("TLabelframe.Label", font=("Microsoft YaHei UI", 12, "bold"))
    style.configure("TCombobox", font=("Microsoft YaHei UI", 11))


def run():
    _enable_high_dpi()  # 必须在创建任何窗口前调用

    logger = init_logger()
    logger.info("ScreenKit 启动中...")
    ensure_runtime_dirs()

    config = load_config()
    app_meta = config.get("app", {})
    logger.info("配置加载完成: %s v%s", app_meta.get("name"), app_meta.get("version"))

    if not find_ffmpeg():
        logger.warning("未找到 ffmpeg，音视频合成与转码功能将不可用")

    root = tk.Tk()
    root.withdraw()
    
    try:
        icon_path = resource_path("assets/icons/screenkit.ico")
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
    except Exception as e:
        logger.debug("加载窗口图标失败: %s", e)

    _apply_theme(root)

    if _HAS_CHECK:
        try:
            check_results = run_first_run_check()
            show_check_dialog_if_needed(root, check_results)
        except Exception as exc:
            logger.warning("首次运行自检失败: %s", exc)

    from app.ui.main_window import MainWindow
    MainWindow(root)
    root.deiconify()
    root.mainloop()
    logger.info("ScreenKit 已退出")
    return 0