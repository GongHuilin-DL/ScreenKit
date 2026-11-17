"""录屏悬浮控制条：无边框、置顶、半透明，支持拖拽与暂停。"""
import time
import tkinter as tk


class FloatingBar(tk.Toplevel):
    def __init__(self, master, on_stop_callback, on_pause_callback):
        super().__init__(master)
        self.on_stop_callback = on_stop_callback
        self.on_pause_callback = on_pause_callback
        
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.85)
        self.configure(bg="#222")
        
        screen_w = self.winfo_screenwidth()
        self.geometry(f"260x44+{screen_w // 2 - 130}+40")
        
        self._start_time = None
        self._accumulated_time = 0.0
        self._pause_start = 0.0
        self._after_id = None
        self._is_paused = False
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build()

    def _build(self):
        self.timer_var = tk.StringVar(value="● 00:00")
        self.lbl_timer = tk.Label(
            self, textvariable=self.timer_var, 
            fg="#ff5252", bg="#222", 
            font=("Microsoft YaHei UI", 12, "bold")
        )
        self.lbl_timer.pack(side="left", padx=(16, 10))

        self.btn_pause = tk.Button(
            self, text="暂停", command=self._toggle_pause,
            bg="#555", fg="white", relief="flat",
            font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2"
        )
        self.btn_pause.pack(side="left", padx=(0, 10), pady=8)

        self.btn_stop = tk.Button(
            self, text="停止", command=self.on_stop_callback,
            bg="#e53935", fg="white", relief="flat",
            font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2"
        )
        self.btn_stop.pack(side="right", padx=(0, 12), pady=8)

        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.lbl_timer.bind("<ButtonPress-1>", self._on_drag_start)
        self.lbl_timer.bind("<B1-Motion>", self._on_drag_motion)

    def _toggle_pause(self):
        self.on_pause_callback()
        self._is_paused = not self._is_paused
        if self._is_paused:
            self.btn_pause.configure(text="继续", bg="#0078d7")
            self._pause_start = time.perf_counter()
        else:
            self.btn_pause.configure(text="暂停", bg="#555")
            self._accumulated_time += time.perf_counter() - self._pause_start

    def start_timer(self):
        self._start_time = time.perf_counter()
        self._accumulated_time = 0.0
        self._is_paused = False
        self.btn_pause.configure(text="暂停", bg="#555")
        self._tick()

    def stop_timer(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self._start_time = None

    def _tick(self):
        if self._start_time is None:
            return
        if not self._is_paused:
            elapsed = time.perf_counter() - self._start_time - self._accumulated_time
            m, s = divmod(int(elapsed), 60)
            self.timer_var.set(f"● {m:02d}:{s:02d}")
        self._after_id = self.after(200, self._tick)

    def _on_drag_start(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        x = self.winfo_x() - self._drag_start_x + event.x
        y = self.winfo_y() - self._drag_start_y + event.y
        self.geometry(f"+{x}+{y}")