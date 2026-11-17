"""命令行验证录屏，不经过 GUI。

用法:
    python tools/quick_record.py --duration 5
    python tools/quick_record.py --duration 5 --region 100,100,800,600 --fps 30
"""
import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.encoding.encoder_config import EncoderConfig
from app.core.models import Rect
from app.core.recording.recorder import Recorder
from app.infra.paths import OUTPUT_DIR, resolve_dir


def _parse_region(text: str) -> Rect:
    try:
        x, y, w, h = (int(p.strip()) for p in text.split(","))
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"区域格式应为 x,y,w,h，收到 {text!r}") from exc
    return Rect(x=x, y=y, width=w, height=h)


def _even(n: int) -> int:
    return n if n % 2 == 0 else n - 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ScreenKit 录屏快速验证")
    parser.add_argument("--duration", type=float, default=5.0, help="录制秒数")
    parser.add_argument("--fps", type=int, default=30, help="帧率")
    parser.add_argument("--region", type=_parse_region, default=None, help="x,y,w,h，不传则录主屏")
    parser.add_argument("--output", default=None, help="输出目录")
    args = parser.parse_args()

    from app.core.capture.screen_capture import ScreenCapture
    from app.infra.config import load_config

    if args.region is not None:
        region = args.region
    else:
        with ScreenCapture() as cap:
            region = cap.primary_monitor_rect()

    # H.264/yuv420p 要求偶数宽高
    region = Rect(region.x, region.y, _even(region.width), _even(region.height))

    config = load_config()
    out_dir = resolve_dir(args.output or config["paths"]["output_dir"])
    out_path = out_dir / f"record_{int(time.time())}.mp4"

    encoder_config = EncoderConfig(
        width=region.width,
        height=region.height,
        fps=args.fps,
        crf=config["recording"].get("crf", 23),
        preset=config["recording"].get("preset", "fast"),
    )

    recorder = Recorder(region, out_path, encoder_config)
    print(f"录制区域: {region}，时长: {args.duration}s，fps: {args.fps}")
    print("开始录制...（按 Ctrl+C 可提前停止）")

    recorder.start()
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n提前停止...")
    finally:
        path = recorder.stop()

    print(f"录制完成: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())