"""命令行验证滚动截图。运行前请把目标窗口（如浏览器）放在前台，
并把鼠标移到目标窗口内。

用法:
    python tools/quick_scrollshot.py --duration 15
    python tools/quick_scrollshot.py --duration 15 --region 100,100,900,700 --step -4
"""
import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.controllers.scrollshot_controller import ScrollShotController
from app.core.models import Rect
from app.infra.paths import resolve_dir


def _parse_region(text: str) -> Rect:
    try:
        x, y, w, h = (int(p.strip()) for p in text.split(","))
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"区域格式应为 x,y,w,h，收到 {text!r}") from exc
    return Rect(x=x, y=y, width=w, height=h)


def main() -> int:
    parser = argparse.ArgumentParser(description="ScreenKit 滚动截图验证")
    parser.add_argument("--region", type=_parse_region, required=True, help="x,y,w,h")
    parser.add_argument("--step", type=int, default=-5, help="滚动步长，负数向下")
    parser.add_argument("--wait", type=float, default=0.5, help="滚动后等待秒数")
    parser.add_argument("--duration", type=float, default=15.0, help="最长运行秒数")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    from app.infra.config import load_config
    config = load_config()
    out_dir = resolve_dir(args.output or config["paths"]["output_dir"])

    controller = ScrollShotController(out_dir)

    def on_progress(count, message):
        print(f"[{count}] {message}")

    print(f"区域: {args.region}，步长: {args.step}，最长 {args.duration}s")
    print("请在 %d 秒内把目标窗口（浏览器）切到前台，鼠标放到窗口内..." % 3)
    time.sleep(3)

    controller.start(args.region, step=args.step, wait=args.wait, progress_callback=on_progress)

    deadline = time.time() + args.duration
    try:
        while controller.is_running and time.time() < deadline:
            time.sleep(0.2)
        if controller.is_running:
            print("达到时间上限，停止滚动...")
            controller.stop()
    except KeyboardInterrupt:
        print("\n用户中断...")
        controller.stop()

    path = controller.wait_and_save("png")
    print(f"长图已保存: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())