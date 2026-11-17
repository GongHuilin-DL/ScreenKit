"""首次运行自检：ffmpeg、音频设备、输出目录可写性。"""
from app.infra.logger import get_logger
from app.infra.paths import OUTPUT_DIR, find_ffmpeg

logger = get_logger("infra.first_run")


def run_first_run_check() -> dict:
    """返回 {check_name: (ok: bool, message: str)}。不抛异常。"""
    results = {}

    # 1. ffmpeg
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        results["ffmpeg"] = (True, f"可用: {ffmpeg}")
    else:
        results["ffmpeg"] = (False, "未找到 ffmpeg，音视频合成与转码将不可用")

    # 2. 输出目录可写
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        probe = OUTPUT_DIR / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        results["output_dir"] = (True, f"可写: {OUTPUT_DIR}")
    except Exception as exc:
        results["output_dir"] = (False, f"输出目录不可写: {exc}")

    # 3. 系统声音 loopback 设备
    try:
        from app.core.audio.device_utils import find_default_loopback_speaker
        speaker = find_default_loopback_speaker()
        if speaker:
            results["loopback"] = (True, f"默认输出设备: {speaker.name}")
        else:
            results["loopback"] = (False, "未找到 loopback 输出设备，系统声音录制可能不可用")
    except Exception as exc:
        results["loopback"] = (False, f"音频设备检查失败: {exc}")

    for name, (ok, msg) in results.items():
        log = logger.info if ok else logger.warning
        log("首次运行自检 [%s]: %s", name, msg)

    return results


def show_check_dialog_if_needed(parent, results: dict) -> None:
    """如果有失败项，弹窗提示。全部通过则不打扰用户。"""
    failures = {k: v for k, v in results.items() if not v[0]}
    if not failures:
        return
    from tkinter import messagebox
    lines = [f"• {msg}" for _, msg in failures.values()]
    messagebox.showwarning(
        "首次运行检查",
        "以下功能可能不可用：\n\n" + "\n".join(lines)
        + "\n\n程序仍可启动，缺失的功能会在对应操作时报错。",
    )