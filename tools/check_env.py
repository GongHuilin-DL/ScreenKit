"""环境自检脚本。

用法:
    python tools/check_env.py

检查项:
    1. Python 版本（需 >= 3.10）
    2. 第三方依赖是否可导入
    3. ffmpeg 是否可用
    4. 音频设备是否可枚举
"""
import importlib
import subprocess
import sys
from pathlib import Path

# 允许脚本从 tools/ 目录直接运行
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# (pip 包名, 导入名, 是否必需)
PACKAGES = [
    ("mss", "mss", True),
    ("av", "av", True),
    ("numpy", "numpy", True),
    ("Pillow", "PIL", True),
    ("opencv-python", "cv2", True),
    ("sounddevice", "sounddevice", True),
    ("soundcard", "soundcard", True),
    ("soundfile", "soundfile", False),
    ("pyautogui", "pyautogui", True),
    ("scrollweave", "scrollweave", False),
    ("PyYAML", "yaml", False),
]

OK, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"


def check_python():
    version = ".".join(str(v) for v in sys.version_info[:3])
    if sys.version_info >= (3, 10):
        return True, f"Python {version}"
    return False, f"Python {version}（需要 >= 3.10）"


def check_package(pip_name, import_name, required):
    try:
        module = importlib.import_module(import_name)
    except ImportError as exc:
        tag = FAIL if required else WARN
        return tag, f"{pip_name:<16} 未安装（{exc}）"
    version = getattr(module, "__version__", "unknown")
    return OK, f"{pip_name:<16} {version}"


def check_ffmpeg():
    from app.infra.paths import find_ffmpeg

    exe = find_ffmpeg()
    if not exe:
        return FAIL, "ffmpeg 未找到（请放入 tools/ffmpeg/ffmpeg.exe 或加入 PATH）"
    try:
        result = subprocess.run(
            [exe, "-version"], capture_output=True, text=True, timeout=10
        )
    except Exception as exc:
        return FAIL, f"ffmpeg 执行失败: {exc}"
    if result.returncode != 0:
        return FAIL, f"ffmpeg 返回码 {result.returncode}"
    first_line = (result.stdout or "").splitlines()[0] if result.stdout else exe
    return OK, first_line.strip()


def check_audio():
    try:
        import sounddevice as sd
    except ImportError:
        return WARN, "sounddevice 未安装，跳过音频设备检查"
    try:
        devices = sd.query_devices()
        default_out = sd.default.device[1]
        return OK, f"检测到 {len(devices)} 个音频设备，默认输出索引 {default_out}"
    except Exception as exc:
        return WARN, f"音频设备枚举失败: {exc}"


def main():
    print("=" * 64)
    print("ScreenKit 环境自检")
    print("=" * 64)

    failed = 0
    warned = 0

    ok, detail = check_python()
    print(f"{OK if ok else FAIL} {detail}")
    failed += 0 if ok else 1

    print("-" * 64)
    print("第三方依赖:")
    for pip_name, import_name, required in PACKAGES:
        tag, detail = check_package(pip_name, import_name, required)
        print(f"{tag} {detail}")
        if tag == FAIL:
            failed += 1
        elif tag == WARN:
            warned += 1

    print("-" * 64)
    tag, detail = check_ffmpeg()
    print(f"{tag} {detail}")
    failed += 1 if tag == FAIL else 0

    tag, detail = check_audio()
    print(f"{tag} {detail}")
    warned += 1 if tag == WARN else 0

    print("=" * 64)
    if failed:
        print(f"结果: {failed} 项失败，{warned} 项警告 —— 请先补齐失败项再进入开发。")
        return 1
    print(f"结果: 全部通过（{warned} 项警告）。可以继续开发。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())