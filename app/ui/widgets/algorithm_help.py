"""滚动截图匹配策略说明窗口。"""
import tkinter as tk
from tkinter import ttk


STRATEGIES = [
    {
        "name": "平衡（推荐）",
        "icon": "⚖️",
        "scene": "大多数普通网页、文档、代码页面。",
        "principle": "灰度模板匹配为主，匹配失败时回退到行签名。",
        "limits": "遇到大面积纯色或重复列表项，可能产生歧义。",
        "tips": "首次使用建议用此策略；如果出现错位，先尝试增大「等待时间」。",
    },
    {
        "name": "快速",
        "icon": "⚡",
        "scene": "纯色背景、表格、大面积留白的页面。",
        "principle": "只使用行签名（一维均值序列）做平移搜索，速度最快。",
        "limits": "丢失水平结构信息，周期性内容可能找到错误的周期。",
        "tips": "适合反复滚动截取同类页面的场景。",
    },
    {
        "name": "鲁棒",
        "icon": "🛡️",
        "scene": "动态广告多、吸顶导航栏明显、单一匹配器不稳的页面。",
        "principle": "模板 → 行签名 → ORB 三级级联，全部失败时才使用上一次有效位移兜底。",
        "limits": "速度最慢，但错位概率最低。",
        "tips": "当「平衡」策略出现明显断层或重复时切换到本策略。",
    },
    {
        "name": "特征点",
        "icon": "🎯",
        "scene": "图片密集、按钮密集、纹理丰富的页面。",
        "principle": "ORB 特征点匹配，用匹配点对的垂直位移中位数估计偏移。",
        "limits": "纯文字长文档、大面积纯色页面提取不到足够特征点。",
        "tips": "不要对维基百科类纯文字页面使用本策略。",
    },
]

GLOBAL_TIP = (
    "提示：滚动截图的质量上限在截图那一刻就已部分决定。\n"
    "让画面在滚动后完全稳定再截下一帧，比任何匹配算法都更有效。\n"
    "如果多次出现错位或断层，优先增大「等待时间」到 0.8 ~ 1.0 秒。"
)


class AlgorithmHelpWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("滚动截图 - 匹配策略说明")
        self.geometry("760x640")
        self.minsize(680, 560)
        self.attributes("-topmost", True)
        self._build()

    def _build(self):
        header = ttk.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill="x")
        ttk.Label(
            header, text="匹配策略说明", font=("Microsoft YaHei UI", 16, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="关闭", command=self.destroy,
        ).pack(side="right")

        body = ttk.Frame(self, padding=(20, 4, 20, 20))
        body.pack(fill="both", expand=True)

        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        for s in STRATEGIES:
            self._render_card(inner, s)

        tip = ttk.Label(
            inner, text=GLOBAL_TIP, foreground="#888",
            font=("Microsoft YaHei UI", 10), justify="left", wraplength=680,
        )
        tip.pack(fill="x", pady=(20, 0))

    def _render_card(self, parent, s):
        card = ttk.LabelFrame(
            parent, text=f"  {s['icon']}  {s['name']}  ", padding=(16, 12, 16, 14),
        )
        card.pack(fill="x", pady=(0, 12))

        for label, key in (
            ("适用场景", "scene"),
            ("原理", "principle"),
            ("已知局限", "limits"),
            ("推荐操作", "tips"),
        ):
            row = ttk.Frame(card)
            row.pack(fill="x", pady=(0, 6))
            ttk.Label(
                row, text=f"{label}：", font=("Microsoft YaHei UI", 10, "bold"),
                width=8, anchor="w",
            ).pack(side="left", anchor="n")
            ttk.Label(
                row, text=s[key], wraplength=600,
                font=("Microsoft YaHei UI", 10), justify="left",
            ).pack(side="left", fill="x", expand=True)