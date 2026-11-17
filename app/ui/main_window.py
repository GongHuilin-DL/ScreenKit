"""主窗口：布局、按钮事件、状态刷新、事件轮询、全局快捷键、系统托盘。"""
import time
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from pynput import keyboard
    _HAS_PYNPUT = True
except ImportError:
    _HAS_PYNPUT = False

try:
    import pystray
    from PIL import Image
    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False

from app.controllers.record_controller import RecordController
from app.controllers.scrollshot_controller import ScrollShotController
from app.controllers.screenshot_controller import ScreenshotController
from app.core.capture.screen_capture import ScreenCapture
from app.infra.config import load_config
from app.infra.events import EventBus, EventType
from app.infra.history import add_record
from app.infra.logger import get_logger
from app.infra.paths import resolve_dir, resource_path
from app.infra.user_config import load_user_config, save_user_config
from app.ui.overlay.region_overlay import RegionOverlay
from app.ui.widgets.control_panel import ControlPanel
from app.ui.widgets.floating_bar import FloatingBar
from app.ui.widgets.history_panel import HistoryPanel
from app.ui.widgets.status_bar import StatusBar

logger = get_logger("ui.main")

MIN_FREE_DISK_BYTES = 200 * 1024 * 1024


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("ScreenKit - 截图与屏幕录制")
        self.root.geometry("960x1200")  # 高度稍作增加以容纳历史面板
        self.root.minsize(960, 1200)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        self.config = load_config()
        self.user_prefs = load_user_config()

        self.output_dir = resolve_dir(
            self.user_prefs.get("output_dir", self.config["paths"]["output_dir"])
        )

        self.event_bus = EventBus()
        self.record_controller = RecordController(self.event_bus, self.output_dir)
        self.screenshot_controller = ScreenshotController(
            self.output_dir,
            quality=self.config["capture"].get("image_quality", 95),
        )
        self.scrollshot_controller = ScrollShotController(self.output_dir)

        self.floating_bar = FloatingBar(self.root, self._on_record_click, self._toggle_record_pause)
        self.floating_bar.withdraw()

        self.tray_icon = None
        self.is_quitting = False

        self._build()
        self._setup_hotkeys()
        self._setup_tray()
        self._schedule_poll()

    def _build(self):
        header = ttk.Frame(self.root, padding=(28, 22, 28, 12))
        header.pack(fill="x")

        ttk.Label(
            header, text="ScreenKit", font=("Microsoft YaHei UI", 24, "bold"),
        ).pack(side="left")
        ttk.Label(
            header, text="截图 · 录屏 · 滚动长图", foreground="#b0b0b0",
            font=("Microsoft YaHei UI", 11),
        ).pack(side="left", padx=(16, 0), pady=(10, 0))

        body = ttk.Frame(self.root, padding=(28, 8, 28, 12))
        body.pack(fill="both", expand=True)
        self.panel = ControlPanel(body, default_values=self.user_prefs)
        self.panel.pack(fill="x")

        # 增加历史记录面板
        self.history_panel = HistoryPanel(body)
        self.history_panel.pack(fill="both", expand=True, pady=(14, 0))

        actions = ttk.Frame(self.root, padding=(28, 0, 28, 16))
        actions.pack(fill="x", side="bottom")

        row1 = ttk.Frame(actions)
        row1.pack(fill="x", pady=(0, 10))
        secondary = [
            ("📷  全屏截图", self._on_full_screenshot),
            ("✂️  区域截图", self._on_region_screenshot),
            ("📜  滚动截图", self._on_scrollshot),
        ]
        for idx, (text, cmd) in enumerate(secondary):
            btn = ttk.Button(
                row1, text=text, command=cmd, style="Secondary.TButton",
            )
            btn.pack(
                side="left", expand=True, fill="x",
                padx=(0 if idx == 0 else 8, 0),
            )

        self.record_btn = ttk.Button(
            actions, text="●  开始录制",
            command=self._on_record_click, style="Accent.TButton",
        )
        self.record_btn.pack(fill="x")

        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(fill="x", side="bottom")

    def _setup_hotkeys(self):
        if not _HAS_PYNPUT:
            logger.warning("未安装 pynput，全局快捷键不可用。")
            return

        self.hotkeys = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+s': self._hotkey_full_screenshot,
            '<ctrl>+<shift>+a': self._hotkey_region_screenshot,
            '<ctrl>+<shift>+r': self._hotkey_record_toggle,
        })
        self.hotkeys.start()
        logger.info("全局快捷键已启动")

    def _setup_tray(self):
        if not _HAS_PYSTRAY:
            logger.warning("未安装 pystray，系统托盘不可用。请执行 pip install pystray pillow")
            return

        icon_path = resource_path("assets/icons/screenkit.ico")
        try:
            image = Image.open(icon_path)
        except Exception:
            logger.warning("托盘图标加载失败，使用纯色备用图标")
            image = Image.new("RGB", (64, 64), color=(25, 118, 210))

        def show_window(icon, item):
            self.root.after(0, self._show_window)

        def full_screenshot(icon, item):
            self.root.after(0, self._on_full_screenshot)

        def region_screenshot(icon, item):
            self.root.after(0, self._on_region_screenshot)

        def record_toggle(icon, item):
            self.root.after(0, self._on_record_click)

        def quit_app(icon, item):
            self.root.after(0, self._real_quit)

        menu = pystray.Menu(
            pystray.MenuItem("显示主界面", show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📷 全屏截图", full_screenshot),
            pystray.MenuItem("✂️ 区域截图", region_screenshot),
            pystray.MenuItem("● 录制开关", record_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出 ScreenKit", quit_app),
        )

        self.tray_icon = pystray.Icon("ScreenKit", image, "ScreenKit - 截图与录屏", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        logger.info("系统托盘已启动")

    def _hotkey_full_screenshot(self):
        self.root.after(0, self._on_full_screenshot)

    def _hotkey_region_screenshot(self):
        self.root.after(0, self._on_region_screenshot)

    def _hotkey_record_toggle(self):
        self.root.after(0, self._on_record_click)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _hide_to_tray(self):
        if self.is_quitting:
            return
            
        if self.record_controller.state in ("recording", "paused"):
            self.root.withdraw()
            return
            
        self.root.withdraw()
        logger.info("主窗口已隐藏到托盘")

    def _real_quit(self):
        self.is_quitting = True

        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

        if _HAS_PYNPUT and hasattr(self, "hotkeys"):
            self.hotkeys.stop()

        state = self.record_controller.state
        if state in ("recording", "paused"):
            if not messagebox.askyesno(
                "确认退出",
                "当前正在录制，退出将丢失未保存的录制内容。继续？",
            ):
                self.is_quitting = False
                return
            try:
                self.record_controller.stop()
            except Exception:
                logger.exception("退出时停止录制失败")
        elif state == "finalizing":
            messagebox.showinfo("请稍候", "正在合成视频，请等待完成后再关闭窗口。")
            self.is_quitting = False
            return

        try:
            current_values = self.panel.get_values()
            save_user_config(current_values)
        except Exception as e:
            logger.warning("保存用户配置失败: %s", e)

        self.root.destroy()

    def _update_output_dir(self) -> bool:
        values = self.panel.get_values()
        new_dir_str = values.get("output_dir")
        if not new_dir_str:
            return True

        new_dir = Path(new_dir_str)
        if self.output_dir != new_dir:
            try:
                new_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.exception("创建输出目录失败")
                messagebox.showerror(
                    "目录错误", f"无法创建或访问目录:\n{new_dir}\n\n{e}"
                )
                return False

            self.output_dir = new_dir
            self.screenshot_controller.output_dir = self.output_dir
            self.record_controller._output_dir = self.output_dir
            self.scrollshot_controller.output_dir = self.output_dir

        return True

    def _check_disk_and_permission(self) -> bool:
        probe = self.output_dir / ".write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception as e:
            logger.exception("输出目录写入权限不足")
            messagebox.showerror(
                "权限错误",
                f"当前输出目录没有写入权限，请更换目录。\n\n目录: {self.output_dir}\n错误: {e}",
            )
            return False

        try:
            _, _, free = shutil.disk_usage(self.output_dir)
            if free < MIN_FREE_DISK_BYTES:
                mb = free // (1024 * 1024)
                ok = messagebox.askyesno(
                    "磁盘空间不足",
                    f"当前磁盘剩余空间仅 {mb} MB，录制过程中可能中断。\n\n是否继续？",
                )
                if not ok:
                    return False
        except Exception as e:
            logger.debug("获取磁盘剩余空间失败: %s", e)

        return True

    def _on_full_screenshot(self):
        if not self._update_output_dir(): return
        if not self._check_disk_and_permission(): return
        
        was_visible = self.root.winfo_ismapped()
        try:
            if was_visible:
                self.root.withdraw()
                self.root.update_idletasks()
                time.sleep(0.15) 
            
            image = self.screenshot_controller.capture_full_screen_image()
        except Exception as exc:
            logger.exception("全屏截图失败")
            messagebox.showerror("截图失败", str(exc))
            if was_visible:
                self.root.deiconify()
            return

        self._open_editor(image)
        
        if was_visible:
            self.root.deiconify()
            self.root.lift()

    def _on_region_screenshot(self):
        if not self._update_output_dir(): return
        if not self._check_disk_and_permission(): return
        
        was_visible = self.root.winfo_ismapped()
        try:
            with ScreenCapture() as cap:
                virtual = cap.virtual_screen_rect()
            
            self.root.withdraw()
            self.root.update_idletasks()
            
            overlay = RegionOverlay(self.root, virtual)
            rect = overlay.select()
            
            if rect is None:
                if was_visible:
                    self.root.deiconify()
                return
                
            image = self.screenshot_controller.capture_region_image(rect)
            
        except Exception as exc:
            logger.exception("区域截图失败")
            messagebox.showerror("截图失败", str(exc))
            if was_visible:
                self.root.deiconify()
            return

        self._open_editor(image)
        
        if was_visible:
            self.root.deiconify()
            self.root.lift()

    def _open_editor(self, image):
        from app.ui.widgets.image_editor import ImageEditorWindow
        fmt = self.panel.get_values()["image_format"]
        
        editor = ImageEditorWindow(self.root, image, self.output_dir, fmt)
        self.root.wait_window(editor)
        
        if editor.saved_path:
            self.status_bar.set_status(f"截图已保存: {editor.saved_path.name}")
            add_record("image", str(editor.saved_path))  # <--- 新增：记录图片历史
            self.history_panel.refresh()                 # <--- 新增：刷新面板
            messagebox.showinfo("截图完成", f"截图已保存:\n{editor.saved_path}")

    def _on_record_click(self):
        state = self.record_controller.state
        if state == "idle":
            self._start_record()
        elif state in ("recording", "paused"):
            self._stop_record()
        else:
            self.status_bar.set_status("正在合成，请稍候...")

    def _toggle_record_pause(self):
        state = self.record_controller.state
        if state == "recording":
            self.record_controller.pause()
            self.status_bar.set_status("录制已暂停")
        elif state == "paused":
            self.record_controller.resume()
            self.status_bar.set_status("录制进行中")

    def _start_record(self):
        if not self._update_output_dir(): return
        if not self._check_disk_and_permission(): return
        
        try:
            rect = self._select_region()
            if rect is None:
                self.status_bar.set_status("已取消录制")
                return
            
            values = self.panel.get_values()
            countdown_sec = values.get("countdown", 3)
            
            def begin_recording():
                try:
                    self.record_controller.start(
                        rect,
                        fps=values["fps"],
                        record_system_audio=values["record_system_audio"],
                        record_microphone=values["record_microphone"],
                        highlight_mouse=values.get("highlight_mouse", True),
                    )
                    self.record_btn.configure(text="■  停止录制")
                    self.panel.set_enabled(False)
                    self.status_bar.start_timer()

                    self.floating_bar.start_timer()
                    self.floating_bar.deiconify()
                    self.root.withdraw()
                except Exception as exc:
                    logger.exception("启动录制失败")
                    messagebox.showerror("录制失败", str(exc))
                    self.status_bar.set_status("录制启动失败")
                    self.record_btn.configure(text="●  开始录制")
                    self.panel.set_enabled(True)

            def cancel_recording():
                self.status_bar.set_status("已取消录制")

            if countdown_sec > 0:
                self.status_bar.set_status(f"倒计时 {countdown_sec} 秒...")
                from app.ui.widgets.countdown_window import CountdownWindow
                CountdownWindow(
                    self.root, 
                    countdown_sec, 
                    on_finish_callback=begin_recording, 
                    on_cancel_callback=cancel_recording
                )
            else:
                begin_recording()

        except Exception as exc:
            logger.exception("录制初始化失败")
            messagebox.showerror("录制失败", str(exc))
            self.status_bar.set_status("录制启动失败")

    def _stop_record(self):
        try:
            self.record_controller.stop()
            self.record_btn.configure(text="⏳  合成中...", state="disabled")
            self.status_bar.stop_timer()
            self.status_bar.set_status("正在合成音视频...")

            self.floating_bar.stop_timer()
            self.floating_bar.withdraw()
        except Exception as exc:
            logger.exception("停止录制失败")
            messagebox.showerror("停止失败", str(exc))

    def _on_scrollshot(self):
        if not self._update_output_dir(): return
        if not self._check_disk_and_permission(): return

        if self.scrollshot_controller.is_running:
            self.scrollshot_controller.stop()
            self.status_bar.set_status("正在停止滚动截图...")
            return
        try:
            rect = self._select_region()
            if rect is None:
                return
            self.root.withdraw()
            self.root.update_idletasks()
            time.sleep(0.5)
            values = self.panel.get_values()

            # 策略中文名 → 枚举
            from app.core.scrollshot.stitcher import MatchStrategy
            strategy_map = {
                "平衡（推荐）": MatchStrategy.BALANCED,
                "快速": MatchStrategy.FAST,
                "鲁棒": MatchStrategy.ROBUST,
                "特征点": MatchStrategy.FEATURE,
            }
            strategy = strategy_map.get(
                values.get("match_strategy", "平衡（推荐）"),
                MatchStrategy.BALANCED,
            )

            self.scrollshot_controller.start(
                rect,
                step=values.get("scroll_step", -5),
                wait=values.get("scroll_wait", 0.5),
                strategy=strategy,
                progress_callback=lambda n, msg: self.root.after(
                    0, lambda: self.status_bar.set_status(msg)
                ),
            )
            self.status_bar.set_status("滚动截图中...（把目标窗口切到前台）")
            self.root.after(100, self._poll_scrollshot)
        except Exception as exc:
            logger.exception("滚动截图启动失败")
            messagebox.showerror("滚动截图失败", str(exc))

    def _poll_scrollshot(self):
        if self.scrollshot_controller.is_running:
            self.root.after(300, self._poll_scrollshot)
            return
        try:
            path = self.scrollshot_controller.wait_and_save(
                self.panel.get_values()["image_format"]
            )
            self.status_bar.set_status(f"滚动截图已保存: {path.name}")
            add_record("image", str(path))  # <--- 新增：记录图片历史
            self.history_panel.refresh()    # <--- 新增：刷新面板
            messagebox.showinfo("截图完成", f"滚动长图已保存:\n{path}")
        except Exception as exc:
            logger.exception("滚动截图失败")
            messagebox.showerror("滚动截图失败", str(exc))

    def _select_region(self):
        was_visible = self.root.winfo_ismapped()

        with ScreenCapture() as cap:
            virtual = cap.virtual_screen_rect()
        
        self.root.withdraw()
        self.root.update_idletasks()
        try:
            overlay = RegionOverlay(self.root, virtual)
            return overlay.select()
        finally:
            if was_visible:
                self.root.deiconify()

    def _schedule_poll(self):
        self.root.after(100, self._poll_events)

    def _poll_events(self):
        for event in self.event_bus.poll():
            self._handle_event(event)
        self._schedule_poll()

    def _handle_event(self, event):
        if event.type == EventType.RECORDING_STARTED:
            self.status_bar.set_status(event.message)
        elif event.type == EventType.RECORDING_STOPPED:
            self.record_btn.configure(text="●  开始录制", state="normal")
            self.panel.set_enabled(True)

            self.floating_bar.withdraw()

            path = event.payload.get("path", "")
            video_fmt = self.panel.get_values()["video_format"]
            
            if path and video_fmt != "mp4":
                try:
                    from app.core.export.transcoder import Transcoder
                    from app.core.export.clipboard_exporter import copy_file_to_clipboard
                    
                    exported = Transcoder().transcode(path, video_fmt)
                    self.status_bar.set_status(f"已导出: {exported.name}")
                    
                    try:
                        import os
                        os.remove(path) # 清理中间 MP4
                    except Exception as e:
                        logger.warning("清理中间 MP4 文件失败: %s", e)

                    copy_file_to_clipboard(exported)
                    tip = "\n\n✅ 已复制到剪贴板，可直接粘贴发送"

                    add_record("video", str(exported))  # <--- 新增：记录视频历史
                    self.history_panel.refresh()        # <--- 新增：刷新面板

                    messagebox.showinfo(
                        "录制完成",
                        f"视频已保存:\n{exported}{tip}",
                    )
                except Exception as exc:
                    logger.exception("转码失败")
                    messagebox.showwarning(
                        "录制完成（转码失败）",
                        f"由于转码失败，仅保留了 MP4:\n{path}\n\n错误信息: {exc}",
                    )
            else:
                self.status_bar.set_status(event.message)
                if path:
                    from app.core.export.clipboard_exporter import copy_file_to_clipboard
                    copy_file_to_clipboard(path)
                    tip = "\n\n✅ 已复制到剪贴板，可直接粘贴发送"
                    
                    add_record("video", str(path))  # <--- 新增：记录视频历史
                    self.history_panel.refresh()    # <--- 新增：刷新面板

                    messagebox.showinfo("录制完成", f"视频已保存到:\n{path}{tip}")
        elif event.type == EventType.RECORDING_FAILED:
            self.record_btn.configure(text="●  开始录制", state="normal")
            self.panel.set_enabled(True)

            self.floating_bar.withdraw()

            self.status_bar.set_status(event.message)
            messagebox.showerror("录制失败", event.message)