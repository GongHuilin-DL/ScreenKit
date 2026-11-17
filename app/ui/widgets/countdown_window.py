"""录屏倒计时全屏遮罩窗口。"""
import tkinter as tk
from app.infra.logger import get_logger

logger = get_logger("ui.countdown")


class CountdownWindow(tk.Toplevel):
    def __init__(self, master, seconds: int, on_finish_callback, on_cancel_callback=None):
        super().__init__(master)
        self.seconds = seconds
        self.on_finish = on_finish_callback
        self.on_cancel = on_cancel_callback
        self.current_count = seconds

        # 窗口属性：无边框、置顶、全屏半透明
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.6)  # 半透明遮罩
        self.configure(bg="black")
        
        # 全屏覆盖
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")

        # 居中显示大号数字
        self.label = tk.Label(
            self, text=str(seconds), 
            fg="#ff5252", bg="black", 
            font=("Microsoft YaHei UI", 120, "bold")
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")

        # 提示文字
        self.tip = tk.Label(
            self, text="录制即将开始...\n(按 Esc 取消)", 
            fg="white", bg="black", 
            font=("Microsoft YaHei UI", 16)
        )
        self.tip.place(relx=0.5, rely=0.7, anchor="center")

        # 绑定取消
        self.bind("<Escape>", self._cancel)
        self.focus_force()

        self._tick()

    def _tick(self):
        if self.current_count <= 0:
            self._finish()
            return
            
        self.label.configure(text=str(self.current_count))
        self.current_count -= 1
        self.after(1000, self._tick)

    def _finish(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.on_finish:
            self.on_finish()

    def _cancel(self, event=None):
        logger.info("用户取消了倒计时")
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.on_cancel:
            self.on_cancel()