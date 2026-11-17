"""状态栏：带分隔线，左侧状态文字，右侧录制计时。"""
import time
import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=(0, 0, 0, 0))

        # 顶部装饰线
        ttk.Separator(self, orient="horizontal").pack(fill="x")

        inner = ttk.Frame(self, padding=(28, 14, 28, 16))
        inner.pack(fill="x")

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(
            inner, textvariable=self.status_var,
            foreground="#aaa", font=("Microsoft YaHei UI", 11), # 字体增大，适配深色
        ).pack(side="left")

        self.timer_var = tk.StringVar(value="")
        self._timer_label = ttk.Label(
            inner, textvariable=self.timer_var,
            foreground="#ff5252", font=("Microsoft YaHei UI", 14, "bold"), # 计时器字体加大加粗
        )
        self._timer_label.pack(side="right")

        self._start_time = None
        self._after_id = None

    def set_status(self, text):
        self.status_var.set(text)

    def start_timer(self):
        self._start_time = time.perf_counter()
        self._tick()

    def stop_timer(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self._start_time = None
        self.timer_var.set("")

    def _tick(self):
        if self._start_time is None:
            return
        elapsed = time.perf_counter() - self._start_time
        minutes, seconds = divmod(int(elapsed), 60)
        self.timer_var.set(f"● {minutes:02d}:{seconds:02d}")
        self._after_id = self.after(200, self._tick)