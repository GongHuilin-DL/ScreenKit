"""自动生成 ScreenKit 的 .ico 图标（无需外部素材）。"""
from pathlib import Path
from PIL import Image, ImageDraw

def create_icon():
    size = 256
    # 背景色使用深灰蓝，与深色主题呼应
    bg_color = (30, 34, 42) 
    # 主题色使用蓝色（对应开始录制按钮）
    accent_color = (25, 118, 210) 
    white = (255, 255, 255)

    # 1. 画背景（圆角矩形）
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, size-8, size-8], radius=48, fill=bg_color)

    # 2. 画屏幕轮廓（外部边框）
    draw.rounded_rectangle([48, 64, 208, 160], radius=12, outline=white, width=10)
    
    # 3. 画屏幕底座
    draw.rectangle([112, 160, 144, 192], fill=white)
    draw.rounded_rectangle([80, 192, 176, 204], radius=6, fill=white)

    # 4. 画屏幕内的“快门/录制”圆点
    draw.ellipse([104, 88, 152, 136], fill=accent_color)
    # 增加一点高光反射效果
    draw.ellipse([114, 98, 126, 110], fill=(255, 255, 255, 150))

    # 5. 保存为 .ico 格式（包含多种尺寸，适配任务栏和桌面）
    icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_path = icon_dir / "screenkit.ico"
    
    img.save(icon_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"图标已生成: {icon_path}")

if __name__ == "__main__":
    create_icon()