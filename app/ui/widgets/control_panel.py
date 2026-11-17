"""参数控件：按功能分卡片，控件两列排布，使用下拉框提供常用预设。"""
import os
import subprocess
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from pathlib import Path

from app.infra.user_config import DEFAULT_USER_PREFS
from app.infra.logger import get_logger

logger = get_logger("ui.control_panel")


class ControlPanel(ttk.Frame):
    """参数面板。三个分组卡片：截图 / 录屏 / 滚动截图。"""

    def __init__(self, master, default_values=None):
        super().__init__(master)
        self._defaults = default_values or DEFAULT_USER_PREFS
        self._build()

    def _build(self):
        self._build_screenshot_card()
        self._build_record_card()
        self._build_scrollshot_card()

    # --- 卡片 1：截图设置 ---
    def _build_screenshot_card(self):
        card = ttk.LabelFrame(self, text="  截图设置  ", padding=(20, 16, 20, 18))
        card.pack(fill="x", pady=(0, 14))

        ttk.Label(card, text="图片格式").grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.image_fmt_var = tk.StringVar(value=str(self._defaults.get("image_format", "png")))
        ttk.Combobox(
            card, textvariable=self.image_fmt_var,
            values=["png", "jpg", "bmp"], state="readonly", width=12,
        ).grid(row=0, column=1, sticky="w", padx=(0, 40))

        ttk.Label(card, text="输出目录").grid(row=0, column=2, sticky="w", padx=(0, 16))
        dir_row = ttk.Frame(card)
        dir_row.grid(row=0, column=3, sticky="w")
        
        self.output_dir_var = tk.StringVar(value=str(self._defaults.get("output_dir", "output")))
        ttk.Entry(
            dir_row, textvariable=self.output_dir_var, 
            state="readonly", width=22
        ).pack(side="left", padx=(0, 8))
        
        ttk.Button(
            dir_row, text="浏览...", command=self._on_browse_dir, width=8
        ).pack(side="left", padx=(0, 4))
        
        ttk.Button(
            dir_row, text="📂 打开", command=self._on_open_dir, width=8
        ).pack(side="left")

    def _on_browse_dir(self):
        current = self.output_dir_var.get()
        if not os.path.exists(current):
            current = os.getcwd()
        
        safe_current = current.replace("'", "''")

        ps_script = f"""
                    Add-Type -AssemblyName System.Windows.Forms
                    $f = New-Object System.Windows.Forms.FolderBrowserDialog
                    $f.Description = '请选择输出目录'
                    $f.SelectedPath = '{safe_current}'
                    $f.ShowNewFolderButton = $true
                    if ($f.ShowDialog() -eq 'OK') {{
                        Write-Output $f.SelectedPath
                    }}
                    """
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=0x08000000
            )
            new_dir = result.stdout.strip()
            if new_dir:
                self.output_dir_var.set(str(Path(new_dir)))
        except Exception as e:
            messagebox.showerror("错误", f"打开目录选择框失败: {e}")

    def _on_open_dir(self):
        current = self.output_dir_var.get()
        if not current:
            return
        path = Path(current)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showwarning("提示", f"目录不存在，且创建失败:\n{path}\n\n错误信息: {e}")
                return
        try:
            os.startfile(str(path.resolve()))
        except Exception as e:
            messagebox.showerror("错误", f"无法打开目录: {e}")
            
    # --- 卡片 2：录屏设置 ---
    def _build_record_card(self):
        card = ttk.LabelFrame(self, text="  录屏设置  ", padding=(20, 16, 20, 18))
        card.pack(fill="x", pady=(0, 14))

        ttk.Label(card, text="帧率 (fps)").grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.fps_var = tk.StringVar(value=str(self._defaults.get("fps", "30")))
        ttk.Combobox(
            card, textvariable=self.fps_var,
            values=["15", "24", "30", "60", "120"], state="readonly", width=12,
        ).grid(row=0, column=1, sticky="w", padx=(0, 40))

        ttk.Label(card, text="视频格式").grid(row=0, column=2, sticky="w", padx=(0, 16))
        self.video_fmt_var = tk.StringVar(value=str(self._defaults.get("video_format", "mp4")))
        ttk.Combobox(
            card, textvariable=self.video_fmt_var,
            values=["mp4", "avi", "wmv"], state="readonly", width=12,
        ).grid(row=0, column=3, sticky="w")

        # 音频
        ttk.Label(card, text="音频").grid(row=1, column=0, sticky="w", padx=(0, 16), pady=(16, 0))
        audio_row = ttk.Frame(card)
        audio_row.grid(row=1, column=1, columnspan=3, sticky="w", pady=(16, 0))
        self.sys_audio_var = tk.BooleanVar(value=bool(self._defaults.get("record_system_audio", True)))
        ttk.Checkbutton(
            audio_row, text="系统声音", variable=self.sys_audio_var,
        ).pack(side="left", padx=(0, 32))
        self.mic_var = tk.BooleanVar(value=bool(self._defaults.get("record_microphone", False)))
        ttk.Checkbutton(
            audio_row, text="麦克风", variable=self.mic_var,
        ).pack(side="left")

        # 倒计时
        ttk.Label(card, text="倒计时").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=(16, 0))
        self.countdown_var = tk.StringVar(value=str(self._defaults.get("countdown", "3")))
        ttk.Combobox(
            card, textvariable=self.countdown_var,
            values=["0", "3", "5", "10"], state="readonly", width=12,
        ).grid(row=2, column=1, sticky="w", pady=(16, 0))
        ttk.Label(
            card, text="秒（录制前留时间切屏）", foreground="#aaa",
        ).grid(row=2, column=2, columnspan=2, sticky="w", pady=(16, 0))

        # 特效
        ttk.Label(card, text="特效").grid(row=3, column=0, sticky="w", padx=(0, 16), pady=(16, 0))
        effect_row = ttk.Frame(card)
        effect_row.grid(row=3, column=1, columnspan=3, sticky="w", pady=(16, 0))
        self.highlight_mouse_var = tk.BooleanVar(value=bool(self._defaults.get("highlight_mouse", True)))
        ttk.Checkbutton(
            effect_row, text="高亮鼠标与点击", variable=self.highlight_mouse_var,
        ).pack(side="left")

    # --- 卡片 3：滚动截图设置 ---
    def _build_scrollshot_card(self):
        card = ttk.LabelFrame(self, text="  滚动截图设置  ", padding=(20, 16, 20, 18))
        card.pack(fill="x")

        # 滚动步长
        ttk.Label(card, text="滚动步长").grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.scroll_step_var = tk.StringVar(value=str(self._defaults.get("scroll_step", "-5")))
        ttk.Combobox(
            card, textvariable=self.scroll_step_var,
            values=["-2", "-3", "-4", "-5", "-6", "-8", "-10"], 
            state="readonly", width=12,
        ).grid(row=0, column=1, sticky="w", padx=(0, 40))
        ttk.Label(
            card, text="（负数向下，-5 约一屏）", foreground="#aaa",
        ).grid(row=0, column=2, columnspan=2, sticky="w")

        # 等待时间
        ttk.Label(card, text="等待时间").grid(row=1, column=0, sticky="w", padx=(0, 16), pady=(16, 0))
        self.scroll_wait_var = tk.StringVar(value=str(self._defaults.get("scroll_wait", "0.5")))
        ttk.Combobox(
            card, textvariable=self.scroll_wait_var,
            values=["0.2", "0.3", "0.5", "0.8", "1.0", "1.5", "2.0"], 
            state="readonly", width=12,
        ).grid(row=1, column=1, sticky="w", pady=(16, 0))
        ttk.Label(
            card, text="秒（页面滚动慢可调大）", foreground="#aaa",
        ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(16, 0))

        # 匹配策略（新增）
        ttk.Label(card, text="匹配策略").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=(16, 0))
        self.match_strategy_var = tk.StringVar(
            value=str(self._defaults.get("match_strategy", "平衡（推荐）"))
        )
        ttk.Combobox(
            card, textvariable=self.match_strategy_var,
            values=["平衡（推荐）", "快速", "鲁棒", "特征点"],
            state="readonly", width=14,
        ).grid(row=2, column=1, sticky="w", pady=(16, 0))
        ttk.Button(
            card, text="❓ 算法说明", command=self._show_algorithm_help, width=14,
        ).grid(row=2, column=2, columnspan=2, sticky="w", pady=(16, 0))

    def _show_algorithm_help(self):
        from app.ui.widgets.algorithm_help import AlgorithmHelpWindow
        AlgorithmHelpWindow(self)

    # --- 接口 ---
    def get_values(self):
        """读取参数，并做安全的类型转换。"""
        try:
            fps = int(self.fps_var.get())
        except ValueError:
            fps = 30
            
        try:
            scroll_step = int(self.scroll_step_var.get())
        except ValueError:
            scroll_step = -5
            
        try:
            scroll_wait = float(self.scroll_wait_var.get())
        except ValueError:
            scroll_wait = 0.5

        try:
            countdown = int(self.countdown_var.get())
        except ValueError:
            countdown = 3

        return {
            "output_dir": self.output_dir_var.get(),
            "fps": fps,
            "image_format": self.image_fmt_var.get(),
            "video_format": self.video_fmt_var.get(),
            "record_system_audio": self.sys_audio_var.get(),
            "record_microphone": self.mic_var.get(),
            "scroll_step": scroll_step,
            "scroll_wait": scroll_wait,
            "countdown": countdown,
            "highlight_mouse": self.highlight_mouse_var.get(),
            "match_strategy": self.match_strategy_var.get(),
        }

    def set_enabled(self, enabled):
        """递归禁用/启用所有子控件。"""
        state = "normal" if enabled else "disabled"
        combo_state = "readonly" if enabled else "disabled"

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox):
                    child.configure(state=combo_state)
                elif isinstance(child, (ttk.Entry, ttk.Button)) and child not in (self.winfo_children()):
                    try:
                        child.configure(state=state)
                    except tk.TclError:
                        pass
                else:
                    try:
                        child.configure(state=state)
                    except tk.TclError:
                        pass
                walk(child)

        walk(self)