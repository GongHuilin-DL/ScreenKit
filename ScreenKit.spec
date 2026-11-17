# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

# 收集 sounddevice, sv-ttk 等资源
sd_datas = collect_data_files("_sounddevice_data") + copy_metadata("sounddevice")
sd_binaries = collect_dynamic_libs("_sounddevice_data")
sd_hidden = ["_sounddevice", "_sounddevice_data"]

sd_hidden.append(
    {"win32": "soundcard.mediafoundation",
     "darwin": "soundcard.coreaudio"}.get(sys.platform, "soundcard.pulseaudio")
)

# PyAV 需要显式收集部分子模块
av_hidden = ["av.audio", "av.video", "av.container", "av.codec"]

# 核心修复：补充 pynput 与 win32 的隐藏依赖
pynput_hidden = [
    "pynput",
    "pynput.keyboard",
    "pynput.mouse",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "pynput._util",
    "pynput._util.win32",
]
win32_hidden = ["win32api", "win32con", "win32gui", "win32clipboard"]

# 收集 Tcl/Tk 和 sv-ttk 主题
def find_tcl_tk():
    try:
        import tkinter
        root = tkinter.Tk()
        tcl_lib = root.tk.exprstring("$tcl_library")
        root.destroy()
    except Exception:
        return None

    tcl_dir = Path(tcl_lib).resolve().parent
    tk_dir = tcl_dir.parent / "tk8.6"
    if not tk_dir.exists():
        tk_dir = tcl_dir.parent / "tk"
    tkinter_pyd = Path(sys.base_prefix) / "DLLs" / "_tkinter.pyd"
    return tcl_dir, tk_dir, tkinter_pyd if tkinter_pyd.exists() else None

tcl_tk = find_tcl_tk()

datas = sd_datas[:]
binaries = sd_binaries[:]
# 合并所有 hiddenimports
hiddenimports = sd_hidden + av_hidden + pynput_hidden + win32_hidden + ["tkinter", "_tkinter", "sv_ttk", "pystray", "pystray._win32"]

# 收集 sv_ttk 主题文件
try:
    datas += collect_data_files("sv_ttk")
except Exception:
    print("[WARN] 未找到 sv_ttk，请确保已执行 pip install sv-ttk")

# 配置文件与图标
datas += [
    ("config/default.yaml", "config"),
    ("assets/icons", "assets/icons"),
]

# ffmpeg 可执行文件（打包后放在内部 ffmpeg 目录，代码 paths.py 已适配）
ffmpeg_src = Path("tools/ffmpeg/ffmpeg.exe")
if ffmpeg_src.is_file():
    binaries += [(str(ffmpeg_src), "ffmpeg")]
else:
    print("[WARN] 未找到 tools/ffmpeg/ffmpeg.exe，合成功能将不可用")

# Tcl/Tk 资源
if tcl_tk is not None:
    tcl_dir, tk_dir, tkinter_pyd = tcl_tk
    if tcl_dir.exists(): datas += [(str(tcl_dir), "tcl")]
    if tk_dir.exists(): datas += [(str(tk_dir), "tk")]
    if tkinter_pyd is not None: binaries += [(str(tkinter_pyd), ".")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "pandas"], # 减小体积
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScreenKit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 程序隐藏控制台
    disable_windowed_traceback=False, # 崩溃时弹窗提示，防止静默退出
    argv_emulation=False,
    icon="assets/icons/screenkit.ico", # 窗口图标
    version="version_info.txt" if Path("version_info.txt").is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ScreenKit",
)