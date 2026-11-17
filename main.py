"""ScreenKit 应用入口。

运行:
    python main.py
"""
import sys
import traceback

from app.bootstrap import run


def main() -> int:
    """返回进程退出码，供脚本或 CI 判断运行结果。"""
    try:
        return run()
    except KeyboardInterrupt:
        print("\n用户中断，正在退出...")
        return 130
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())