"""历史记录面板：展示最近的截图和录屏，支持批量清理。"""
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from app.infra.history import load_history, remove_record, clear_missing_records, delete_records
from app.infra.logger import get_logger

logger = get_logger("ui.history")


class HistoryPanel(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text="  最近文件  ", padding=(12, 8, 12, 12))
        self._build()

    def _build(self):
        # 1. 顶部工具栏
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", side="top", pady=(0, 5))
        
        # 左侧常规操作
        ttk.Button(top_frame, text="🔄 刷新", command=self.refresh).pack(side="left", padx=(0, 8))
        ttk.Button(top_frame, text="🧹 清理无效", command=self._clear_missing).pack(side="left")
        
        # 右侧危险操作
        ttk.Button(top_frame, text="🗑️ 删除全部", command=lambda: self._delete_all(None)).pack(side="right", padx=(8, 0))
        ttk.Button(top_frame, text="🗑️ 删视频", command=lambda: self._delete_all("video")).pack(side="right", padx=(8, 0))
        ttk.Button(top_frame, text="🗑️ 删图片", command=lambda: self._delete_all("image")).pack(side="right")

        # 2. 表格区域
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        columns = ("status", "time", "type", "name")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=6, selectmode="browse"
        )
        
        self.tree.heading("status", text="状态")
        self.tree.heading("time", text="时间")
        self.tree.heading("type", text="类型")
        self.tree.heading("name", text="文件名")
        
        self.tree.column("status", width=70, anchor="center")
        self.tree.column("time", width=130, anchor="center")
        self.tree.column("type", width=60, anchor="center")
        self.tree.column("name", width=360, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 配置“已丢失”记录的灰色样式
        self.tree.tag_configure("missing", foreground="gray")

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="打开文件", command=self._open_selected)
        self.menu.add_command(label="打开所在目录", command=self._open_dir)
        self.menu.add_separator()
        self.menu.add_command(label="移除记录", command=self._remove_selected)
        self.menu.add_command(label="清理所有已丢失记录", command=self._clear_missing)

        self.refresh()

    def refresh(self):
        """重新加载历史记录到界面，并校验文件状态。"""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        records = load_history()
        for idx, rec in enumerate(records):
            path = Path(rec.get("path", ""))
            is_missing = False
            
            if not path.is_file():
                is_missing = True
            elif "size" in rec and path.stat().st_size != rec["size"]:
                is_missing = True

            status_text = "❌ 已丢失" if is_missing else "✅ 正常"
            rtype = "🖼️ 图片" if rec.get("type") == "image" else "🎬 视频"
            
            tags = ()
            if is_missing:
                tags = ("missing",)
            
            self.tree.insert(
                "", "end", 
                iid=str(idx), 
                values=(status_text, rec.get("time", ""), rtype, rec.get("name", "")),
                tags=(rec.get("path", ""),) + tags
            )

    def _mark_item_missing(self, item_id: str, rec: dict):
        """将一个条目动态标记为已丢失。"""
        self.tree.set(item_id, "status", "❌ 已丢失")
        self.tree.item(item_id, tags=(rec.get("path", ""), "missing"))

    def _get_selected_record(self) -> tuple[str, dict] | None:
        """返回选中行的 (item_id, record)。"""
        selected = self.tree.selection()
        if not selected:
            return None
        item_id = selected[0]
        tags = self.tree.item(item_id, "tags")
        if not tags:
            return None
            
        path_str = tags[0]
        records = load_history()
        for rec in records:
            if rec.get("path") == path_str:
                return item_id, rec
        return None

    def _open_selected(self):
        result = self._get_selected_record()
        if not result: return
        item_id, rec = result
        
        path = Path(rec["path"])
        is_missing = False
        
        if not path.is_file():
            is_missing = True
        elif "size" in rec and path.stat().st_size != rec["size"]:
            is_missing = True
            
        if is_missing:
            self._mark_item_missing(item_id, rec)
            messagebox.showwarning("文件丢失", f"该文件已丢失或被修改:\n{path}")
            return
            
        try:
            os.startfile(str(path))
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开文件: {e}")

    def _open_dir(self):
        result = self._get_selected_record()
        if not result: return
        item_id, rec = result
        
        path = Path(rec["path"])
        if path.exists():
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            self._mark_item_missing(item_id, rec)
            if path.parent.exists():
                subprocess.Popen(f'explorer "{path.parent}"')
            else:
                messagebox.showwarning("目录不存在", f"目录也不存在:\n{path.parent}")

    def _remove_selected(self):
        result = self._get_selected_record()
        if not result: return
        _, rec = result
        
        remove_record(rec["path"])
        self.refresh()

    def _clear_missing(self):
        count = clear_missing_records()
        if count > 0:
            self.refresh()
            messagebox.showinfo("清理完成", f"已清理 {count} 条无效记录。")
        else:
            messagebox.showinfo("清理完成", "没有发现无效记录。")

    def _delete_all(self, record_type: str | None):
        """从硬盘删除并移除对应记录。record_type 为 None 时代表所有。"""
        records = load_history()
        to_delete = [r for r in records if record_type is None or r.get("type") == record_type]
        
        if not to_delete:
            type_str = "记录" if record_type is None else ("图片" if record_type == "image" else "视频")
            messagebox.showinfo("提示", f"没有可删除的{type_str}。")
            return

        type_str = "所有文件及记录" if record_type is None else ("所有图片" if record_type == "image" else "所有视频")
        msg = f"确定要删除{type_str}吗？\n\n⚠️ 警告：这将从硬盘上永久删除这些文件！\n共 {len(to_delete)} 个文件。\n\n此操作不可撤销，是否继续？"
        
        if not messagebox.askyesno("确认删除", msg, icon="warning"):
            return
            
        count = delete_records(record_type, delete_files=True)
        self.refresh()
        messagebox.showinfo("删除完成", f"已成功删除 {count} 个文件。")

    def _on_double_click(self, event):
        self._open_selected()

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)