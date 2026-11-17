"""快速标注窗口：支持画矩形、箭头、马赛克、文字（自适应窗口+漫游平移+居中显示）。"""
import math
import tkinter as tk
from tkinter import ttk, colorchooser, simpledialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
import cv2

from app.infra.logger import get_logger

logger = get_logger("ui.image_editor")


class ImageEditorWindow(tk.Toplevel):
    def __init__(self, parent, image: Image.Image, save_dir: Path, default_fmt: str):
        super().__init__(parent)
        self.original_image = image.copy()
        self.image = image.copy()
        self.save_dir = save_dir
        self.default_fmt = default_fmt
        self.saved_path = None

        self.title("截图标注 - 完成后请点击保存")
        self.attributes("-topmost", True)

        # 窗口尺寸计算：保证工具栏不被挤压（最小 680 宽）
        min_w = 680
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        init_w = max(min_w, min(image.width, screen_w - 100))
        init_h = min(image.height + 60, screen_h - 100)

        x = max(0, (screen_w - init_w) // 2)
        y = max(0, (screen_h - init_h) // 2)
        self.geometry(f"{init_w}x{init_h}+{x}+{y}")
        self.minsize(min_w, 300)
        self.resizable(True, True)

        # --- 状态机 ---
        self.current_tool = "browse"  # 默认漫游状态
        self.current_color = "#e53935"
        self.history = []
        self.start_x = 0
        self.start_y = 0
        self.preview_shape = None

        # 用于漫游平移
        self._pan_start_x = 0
        self._pan_start_y = 0

        # 图片相对于 Canvas 的居中偏移
        self.off_x = 0
        self.off_y = 0
        self._last_canvas_w = 0
        self._last_canvas_h = 0

        self._build_ui()
        self._bind_events()
        # 默认选中漫游工具
        self._set_tool("browse")
        self.after(50, self.update_canvas)

    def _build_ui(self):
        # 工具栏
        toolbar = tk.Frame(self, bg="#2b2b2b", pady=5)
        toolbar.pack(fill="x", side="top")

        btn_style = {"bg": "#3c3c3c", "fg": "white", "relief": "flat", "padx": 10, "pady": 4}
        
        # 漫游按钮
        self.btn_browse = tk.Button(toolbar, text="👆 漫游", command=lambda: self._set_tool("browse"), **btn_style)
        self.btn_browse.pack(side="left", padx=5)
        
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=5)

        self.btn_rect = tk.Button(toolbar, text="▭ 矩形", command=lambda: self._set_tool("rect"), **btn_style)
        self.btn_rect.pack(side="left", padx=5)
        
        self.btn_arrow = tk.Button(toolbar, text="↗ 箭头", command=lambda: self._set_tool("arrow"), **btn_style)
        self.btn_arrow.pack(side="left", padx=5)

        self.btn_mosaic = tk.Button(toolbar, text="▩ 马赛克", command=lambda: self._set_tool("mosaic"), **btn_style)
        self.btn_mosaic.pack(side="left", padx=5)

        self.btn_text = tk.Button(toolbar, text="T 文字", command=lambda: self._set_tool("text"), **btn_style)
        self.btn_text.pack(side="left", padx=5)

        tk.Button(toolbar, text="🎨 颜色", command=self._choose_color, **btn_style).pack(side="left", padx=15)

        tk.Button(toolbar, text="↩ 撤销", command=self._undo, **btn_style).pack(side="right", padx=5)
        tk.Button(toolbar, text="💾 保存 (Enter)", command=self._save, bg="#e53935", fg="white", relief="flat", padx=10, pady=4).pack(side="right", padx=5)
        tk.Button(toolbar, text="取消 (Esc)", command=self.destroy, **btn_style).pack(side="right", padx=5)

        # 画布区域（带滚动条）
        canvas_frame = tk.Frame(self, bg="black")
        canvas_frame.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg="black", highlightthickness=0)
        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

    def _bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        
        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-z>", lambda e: self._undo())

    def _on_canvas_resize(self, event):
        if abs(event.width - self._last_canvas_w) > 5 or abs(event.height - self._last_canvas_h) > 5:
            self._last_canvas_w = event.width
            self._last_canvas_h = event.height
            self.update_canvas()

    def _set_tool(self, tool):
        self.current_tool = tool
        
        # 重置所有按钮颜色
        for btn in [self.btn_browse, self.btn_rect, self.btn_arrow, self.btn_mosaic, self.btn_text]:
            btn.configure(bg="#3c3c3c")
            
        # 高亮当前按钮并设置光标
        if tool == "browse":
            self.btn_browse.configure(bg="#0078d7")
            self.canvas.configure(cursor="fleur")  # 抓手光标
        else:
            self.canvas.configure(cursor="cross")  # 十字准星光标
            if tool == "rect": self.btn_rect.configure(bg="#0078d7")
            elif tool == "arrow": self.btn_arrow.configure(bg="#0078d7")
            elif tool == "mosaic": self.btn_mosaic.configure(bg="#0078d7")
            elif tool == "text": self.btn_text.configure(bg="#0078d7")

    def _choose_color(self):
        # 1. 防止连点导致弹出多个对话框
        if getattr(self, "_is_color_dialog_open", False):
            return
        self._is_color_dialog_open = True
        
        # 2. 临时取消主窗口的置顶，让颜色对话框能显示在最前面
        self.attributes("-topmost", False)
        
        try:
            # 3. 指定 parent=self，确保归属关系正确
            color = colorchooser.askcolor(
                title="选择颜色", 
                color=self.current_color, 
                parent=self
            )[1]
            if color:
                self.current_color = color
        finally:
            # 4. 无论成功还是取消，都恢复置顶并释放锁
            self.attributes("-topmost", True)
            self._is_color_dialog_open = False

    def _get_image_coords(self, event):
        """将鼠标事件坐标转换为图片内部的真实像素坐标。"""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        ix = cx - self.off_x
        iy = cy - self.off_y
        ix = int(max(0, min(ix, self.image.width)))
        iy = int(max(0, min(iy, self.image.height)))
        return ix, iy

    def update_canvas(self):
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas.delete("all")

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1: cw = self.image.width
        if ch <= 1: ch = self.image.height

        if cw > self.image.width:
            self.off_x = (cw - self.image.width) // 2
        else:
            self.off_x = 0
            
        if ch > self.image.height:
            self.off_y = (ch - self.image.height) // 2
        else:
            self.off_y = 0

        self.canvas.create_image(self.off_x, self.off_y, image=self.photo, anchor="nw")

        scroll_w = max(cw, self.image.width + self.off_x * 2)
        scroll_h = max(ch, self.image.height + self.off_y * 2)
        self.canvas.config(scrollregion=(0, 0, scroll_w, scroll_h))

    def _save_snapshot(self):
        self.history.append(self.image.copy())
        if len(self.history) > 30:
            self.history.pop(0)

    def _undo(self):
        if self.history:
            self.image = self.history.pop()
            self.update_canvas()

    # --- 鼠标事件处理 ---
    def _on_press(self, event):
        if self.current_tool == "browse":
            # 漫游状态：记录起始坐标用于平移
            self._pan_start_x = event.x
            self._pan_start_y = event.y
            self.canvas.scan_mark(event.x, event.y)
            return

        # 编辑状态
        self.start_x, self.start_y = self._get_image_coords(event)
        if self.current_tool == "text":
            self._add_text(self.start_x, self.start_y)

    def _on_drag(self, event):
        if self.current_tool == "browse":
            # 漫游状态：执行平移
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            return

        # 编辑状态
        if self.current_tool in ("text", "mosaic"):
            return

        if self.preview_shape:
            self.canvas.delete(self.preview_shape)

        x1, y1 = self.start_x, self.start_y
        x2, y2 = self._get_image_coords(event)

        cx1, cy1 = x1 + self.off_x, y1 + self.off_y
        cx2, cy2 = x2 + self.off_x, y2 + self.off_y

        if self.current_tool == "rect":
            self.preview_shape = self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=self.current_color, width=3)
        elif self.current_tool == "arrow":
            self.preview_shape = self.canvas.create_line(cx1, cy1, cx2, cy2, fill=self.current_color, width=3, arrow=tk.LAST, arrowshape=(16, 20, 6))

    def _on_release(self, event):
        if self.current_tool == "browse":
            return

        if self.current_tool == "text":
            return

        if self.preview_shape:
            self.canvas.delete(self.preview_shape)
            self.preview_shape = None

        x1, y1 = self.start_x, self.start_y
        x2, y2 = self._get_image_coords(event)

        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            return

        self._save_snapshot()
        draw = ImageDraw.Draw(self.image)

        if self.current_tool == "rect":
            draw.rectangle([min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)], outline=self.current_color, width=3)
        elif self.current_tool == "arrow":
            self._draw_arrow(draw, x1, y1, x2, y2, self.current_color)
        elif self.current_tool == "mosaic":
            self._apply_mosaic(x1, y1, x2, y2)

        self.update_canvas()

    # --- 工具实现 ---
    def _draw_arrow(self, draw, x1, y1, x2, y2, color):
        draw.line((x1, y1, x2, y2), fill=color, width=3)
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_len = 15
        arrow_angle = math.pi / 6
        xA = x2 - arrow_len * math.cos(angle - arrow_angle)
        yA = y2 - arrow_len * math.sin(angle - arrow_angle)
        xB = x2 - arrow_len * math.cos(angle + arrow_angle)
        yB = y2 - arrow_len * math.sin(angle + arrow_angle)
        draw.polygon([(x2, y2), (xA, yA), (xB, yB)], fill=color)

    def _apply_mosaic(self, x1, y1, x2, y2):
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        if x2 - x1 < 5 or y2 - y1 < 5: return
        
        img_cv = cv2.cvtColor(np.array(self.image), cv2.COLOR_RGB2BGR)
        roi = img_cv[y1:y2, x1:x2]
        block = 15
        w, h = max(1, (x2-x1)//block), max(1, (y2-y1)//block)
        roi = cv2.resize(roi, (w, h), interpolation=cv2.INTER_NEAREST)
        roi = cv2.resize(roi, (x2-x1, y2-y1), interpolation=cv2.INTER_NEAREST)
        img_cv[y1:y2, x1:x2] = roi
        self.image = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))

    def _add_text(self, x, y):
        self.attributes("-topmost", False)
        try:
            text = simpledialog.askstring("输入文字", "请输入要标注的文字:", parent=self)
        finally:
            self.attributes("-topmost", True)
            
        if not text: return
        
        self._save_snapshot()
        draw = ImageDraw.Draw(self.image)
        try:
            font = ImageFont.truetype("msyh.ttc", 28)
        except Exception:
            font = ImageFont.load_default()
            
        draw.text((x, y), text, fill=self.current_color, font=font)
        self.update_canvas()

    def _save(self):
        from datetime import datetime
        from app.core.export.image_exporter import ImageExporter
        from app.core.export.clipboard_exporter import copy_image_to_clipboard
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"edited_{timestamp}.{self.default_fmt}"
        path = self.save_dir / filename
        
        try:
            arr = np.array(self.image)[:, :, ::-1]
            self.saved_path = ImageExporter.save(arr, path, fmt=self.default_fmt)
            copy_image_to_clipboard(self.image)
            self.destroy()
        except Exception as e:
            logger.exception("保存标注图片失败")
            messagebox.showerror("保存失败", str(e), parent=self)