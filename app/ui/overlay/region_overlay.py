"""全屏半透明遮罩选区，覆盖虚拟桌面，支持跨显示器。"""
import tkinter as tk

from app.core.models import Rect
from app.infra.logger import get_logger

logger = get_logger("ui.overlay")


class RegionOverlay:
    """模态区域选择器。

    用法:
        overlay = RegionOverlay(root, virtual_rect)
        rect = overlay.select()   # 阻塞直到用户完成或取消
    """

    def __init__(self, root, virtual_rect):
        self._root = root
        self._rect = virtual_rect
        self._result = None
        self._start_x = None
        self._start_y = None
        self._rect_id = None
        self._window = None
        self._canvas = None

    def select(self):
        """显示遮罩并等待用户操作，返回 Rect 或 None（取消）。"""
        self._build()
        try:
            self._root.wait_window(self._window)
        finally:
            self._window = None
            self._canvas = None
        return self._result

    def _build(self):
        r = self._rect
        self._window = tk.Toplevel(self._root)
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.attributes("-alpha", 0.3)
        self._window.configure(bg="black")
        self._window.geometry(f"{r.width}x{r.height}+{r.x}+{r.y}")

        self._canvas = tk.Canvas(
            self._window, bg="black", cursor="cross", highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

        self._window.bind("<Escape>", self._on_cancel)
        self._window.focus_force()
        self._window.grab_set()

    def _on_press(self, event):
        self._start_x = event.x
        self._start_y = event.y
        if self._rect_id:
            self._canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event):
        if self._start_x is None:
            return
        if self._rect_id:
            self._canvas.delete(self._rect_id)
        self._rect_id = self._canvas.create_rectangle(
            self._start_x, self._start_y, event.x, event.y,
            outline="red", width=2,
        )

    def _on_release(self, event):
        if self._start_x is None:
            return
        x1, y1 = self._start_x, self._start_y
        x2, y2 = event.x, event.y
        # 忽略误触的小矩形
        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            self._start_x = None
            return
        local = Rect.from_ltrb(x1, y1, x2, y2)
        r = self._rect
        self._result = Rect(
            x=r.x + local.x, y=r.y + local.y,
            width=local.width, height=local.height,
        )
        self._close()

    def _on_cancel(self, event=None):
        self._result = None
        self._close()

    def _close(self):
        if self._window:
            try:
                self._window.grab_release()
            except tk.TclError:
                pass
            self._window.destroy()