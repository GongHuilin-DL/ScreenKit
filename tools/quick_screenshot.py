"""命令行快速验证截图功能，不经过 GUI。

用法:
    python tools/quick_screenshot.py
    python tools/quick_screenshot.py --region 100,100,800,600
    python tools/quick_screenshot.py --format jpg --output output/shot
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.controllers.screenshot_controller import ScreenshotController
from app.core.models import Rect


def _parse_region(text: str) -> Rect:
    try:
        x, y, w, h = (int(part.strip()) for part in text.split(","))
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"区域格式应为 x,y,w,h，收到 {text!r}") from exc
    return Rect(x=x, y=y, width=w, height=h)


def main() -> int:
    parser = argparse.ArgumentParser(description="ScreenKit 截图快速验证")
    parser.add_argument("--region", type=_parse_region, default=None,
                        help="区域截图，格式 x,y,w,h。不传则截主屏全屏")
    parser.add_argument("--format", default="png", choices=["png", "jpg", "bmp"],
                        help="图片格式，默认 png")
    parser.add_argument("--output", default=None,
                        help="输出目录，默认使用配置中的 output")
    args = parser.parse_args()

    from app.infra.config import load_config
    config = load_config()
    output_dir = args.output or config["paths"]["output_dir"]

    controller = ScreenshotController(output_dir)
    if args.region:
        saved = controller.capture_region(args.region, fmt=args.format)
    else:
        saved = controller.capture_full_screen(fmt=args.format)

    print(f"截图已保存: {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())