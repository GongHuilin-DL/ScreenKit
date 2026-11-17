"""音频设备枚举：列出可用输出设备、查找 loopback 麦克风、列出麦克风输入。"""
from dataclasses import dataclass

from app.infra.logger import get_logger

logger = get_logger("audio.devices")


@dataclass
class SpeakerInfo:
    """一个可录音的输出设备（扬声器/耳机）。"""

    id: str          # soundcard 的设备 ID
    name: str
    is_loopback: bool


@dataclass
class MicInfo:
    """一个麦克风输入设备。"""

    index: int       # sounddevice 的设备索引
    name: str
    channels: int


def list_loopback_speakers() -> list[SpeakerInfo]:
    """列出所有可以通过 loopback 录音的输出设备。

    依赖 soundcard。如果未安装或枚举失败，返回空列表而不是抛异常，
    让上层可以优雅降级到"仅麦克风"模式。
    """
    try:
        import soundcard as sc
    except ImportError:
        logger.warning("soundcard 未安装，无法枚举 loopback 设备")
        return []

    result: list[SpeakerInfo] = []
    try:
        for speaker in sc.all_speakers():
            result.append(
                SpeakerInfo(id=str(speaker.id), name=speaker.name, is_loopback=True)
            )
    except Exception:
        logger.exception("枚举 loopback 设备失败")
    return result


def find_default_loopback_speaker() -> SpeakerInfo | None:
    """返回系统默认输出设备对应的 loopback 入口，找不到返回 None。"""
    try:
        import soundcard as sc
    except ImportError:
        return None
    try:
        default = sc.default_speaker()
        if default is None:
            return None
        return SpeakerInfo(id=str(default.id), name=default.name, is_loopback=True)
    except Exception:
        logger.exception("获取默认 loopback 设备失败")
        return None


def list_microphones() -> list[MicInfo]:
    """列出 sounddevice 可见的麦克风输入设备。"""
    try:
        import sounddevice as sd
    except ImportError:
        logger.warning("sounddevice 未安装，无法枚举麦克风")
        return []

    result: list[MicInfo] = []
    try:
        for index, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                result.append(
                    MicInfo(
                        index=index,
                        name=dev.get("name", f"device-{index}"),
                        channels=int(dev["max_input_channels"]),
                    )
                )
    except Exception:
        logger.exception("枚举麦克风失败")
    return result