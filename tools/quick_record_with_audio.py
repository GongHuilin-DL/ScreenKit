"""端到端验证：录屏 + 系统声音 → 带声音的 MP4。

用法:
    python tools/quick_record_with_audio.py --duration 5
    python tools/quick_record_with_audio.py --duration 5 --mic
    python tools/quick_record_with_audio.py --duration 5 --region 100,100,640,480
"""
import argparse
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.audio.microphone import MicrophoneRecorder
from app.core.audio.system_audio import SystemAudioRecorder
from app.core.encoding.encoder_config import EncoderConfig
from app.core.export.muxer import Muxer
from app.core.models import Rect
from app.core.recording.recorder import Recorder
from app.infra.paths import resolve_dir


def _parse_region(text: str) -> Rect:
    try:
        x, y, w, h = (int(p.strip()) for p in text.split(","))
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"区域格式应为 x,y,w,h，收到 {text!r}") from exc
    return Rect(x=x, y=y, width=w, height=h)


def _even(n: int) -> int:
    return n if n % 2 == 0 else n - 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ScreenKit 带音频录制验证")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--region", type=_parse_region, default=None)
    parser.add_argument("--mic", action="store_true", help="同时录制麦克风")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    from app.core.capture.screen_capture import ScreenCapture
    from app.infra.config import load_config

    config = load_config()
    out_dir = resolve_dir(args.output or config["paths"]["output_dir"])
    stamp = int(time.time())
    final_path = out_dir / f"record_av_{stamp}.mp4"

    if args.region is not None:
        region = args.region
    else:
        with ScreenCapture() as cap:
            region = cap.primary_monitor_rect()
    region = Rect(region.x, region.y, _even(region.width), _even(region.height))

    with tempfile.TemporaryDirectory(prefix="screenkit_") as tmp:
        tmp_dir = Path(tmp)
        silent_video = tmp_dir / "silent.mp4"
        sys_wav = tmp_dir / "system.wav"
        mic_wav = tmp_dir / "mic.wav"

        enc_cfg = EncoderConfig(
            width=region.width,
            height=region.height,
            fps=args.fps,
            crf=config["recording"].get("crf", 23),
            preset=config["recording"].get("preset", "fast"),
        )

        recorder = Recorder(region, silent_video, enc_cfg)
        sys_audio = SystemAudioRecorder()
        mic_audio = MicrophoneRecorder() if args.mic else None

        print(f"录制区域: {region}，时长: {args.duration}s，fps: {args.fps}")
        print("开始录制（系统声音" + (" + 麦克风" if args.mic else "") + "）...")

        recorder.start()
        sys_audio.start(sys_wav, sample_rate=48000, channels=2)
        if mic_audio is not None:
            mic_audio.start(mic_wav, sample_rate=48000, channels=1)

        try:
            time.sleep(args.duration)
        except KeyboardInterrupt:
            print("\n提前停止...")
        finally:
            # 先停录屏，再停音频；合成时 -shortest 会按最短流截断
            recorder.stop()
            sys_audio.stop()
            if mic_audio is not None:
                mic_audio.stop()

        print("正在合成音视频...")
        muxer = Muxer()
        if mic_audio is not None and mic_wav.is_file():
            muxer.mux_mixed(silent_video, sys_wav, mic_wav, final_path)
        else:
            muxer.mux_single(silent_video, sys_wav, final_path)

    print(f"完成: {final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())