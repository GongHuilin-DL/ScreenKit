"""剪贴板导出：支持将图片或文件复制到系统剪贴板。"""
import io
import subprocess
from pathlib import Path
from PIL import Image

try:
    import win32clipboard
    _HAS_WIN32 = True
except ImportError:
    win32clipboard = None
    _HAS_WIN32 = False

from app.infra.logger import get_logger

logger = get_logger("export.clipboard")


def copy_image_to_clipboard(image: Image.Image) -> bool:
    """将 PIL Image 复制到 Windows 剪贴板（DIB 格式）。"""
    if not _HAS_WIN32:
        logger.warning("未安装 pywin32，无法复制图片到剪贴板")
        return False
        
    try:
        output = io.BytesIO()
        # 转换为 RGB 并保存为 BMP 格式
        image.convert("RGB").save(output, "BMP")
        # 剪贴板需要的 DIB 格式就是去掉 BMP 文件头（14 字节）的剩余部分
        data = output.getvalue()[14:]
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        logger.info("图片已复制到剪贴板")
        return True
    except Exception as e:
        logger.exception("复制图片到剪贴板失败: %s", e)
        # 确保剪贴板被释放，防止锁死
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
        return False


def copy_file_to_clipboard(file_path: str | Path) -> bool:
    """将文件复制到 Windows 剪贴板（用于在其他地方直接 Ctrl+V 粘贴文件）。"""
    path = Path(file_path).resolve()
    if not path.is_file():
        return False

    # 使用 PowerShell 的 Set-Clipboard 命令最稳定，且支持长中文路径
    ps_script = f"Set-Clipboard -Path '{str(path)}'"
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        logger.info("文件已复制到剪贴板: %s", path.name)
        return True
    except Exception as e:
        logger.exception("复制文件到剪贴板失败: %s", e)
        return False