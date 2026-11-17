"""枚举音频设备，帮助选择 loopback 设备与麦克风。

用法:
    python tools/list_audio_devices.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.audio.device_utils import (
    find_default_loopback_speaker,
    list_loopback_speakers,
    list_microphones,
)


def main() -> int:
    print("=" * 64)
    print("可录音的输出设备（loopback）")
    print("=" * 64)
    speakers = list_loopback_speakers()
    if not speakers:
        print("未找到。请确认已安装 soundcard: pip install soundcard")
    for sp in speakers:
        print(f"  id={sp.id}")
        print(f"     name={sp.name}")

    default = find_default_loopback_speaker()
    print()
    print(f"默认 loopback 设备: {default.name if default else '无'}")

    print()
    print("=" * 64)
    print("麦克风输入设备（sounddevice）")
    print("=" * 64)
    mics = list_microphones()
    if not mics:
        print("未找到。请确认已安装 sounddevice: pip install sounddevice")
    for mic in mics:
        print(f"  [{mic.index}] {mic.name}  ({mic.channels} ch)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())