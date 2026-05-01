#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成应用图标（兼容旧版 Pillow）
"""

from PIL import Image, ImageDraw
import os

# ============================================================================
# 配置参数
# ============================================================================
ICON_SIZE = 512
BG_COLOR = "#1AAD19"
ENVELOPE_COLOR = "white"
LIGHTNING_COLOR = "#FFD700"
OUTPUT_FILE = "app_icon.png"

# 兼容不同版本的 Pillow 重采样滤镜
try:
    from PIL.Image import Resampling
    RESAMPLE_FILTER = Resampling.LANCZOS
except ImportError:
    try:
        from PIL.Image import LANCZOS
        RESAMPLE_FILTER = LANCZOS
    except ImportError:
        RESAMPLE_FILTER = Image.LANCZOS


# ============================================================================
# 绘制函数
# ============================================================================
def create_icon():
    """生成应用图标"""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    margin = int(ICON_SIZE * 0.08)
    center = ICON_SIZE // 2
    
    # 圆角背景
    bg_radius = int(ICON_SIZE * 0.2)
    draw.rounded_rectangle(
        [(margin, margin), (ICON_SIZE - margin, ICON_SIZE - margin)],
        radius=bg_radius,
        fill=BG_COLOR
    )
    
    # 信封主体
    envelope_width = int(ICON_SIZE * 0.5)
    envelope_height = int(ICON_SIZE * 0.35)
    envelope_left = center - envelope_width // 2
    envelope_top = center - envelope_height // 2 + int(ICON_SIZE * 0.03)
    envelope_right = envelope_left + envelope_width
    envelope_bottom = envelope_top + envelope_height
    
    envelope_radius = int(ICON_SIZE * 0.03)
    draw.rounded_rectangle(
        [(envelope_left, envelope_top), (envelope_right, envelope_bottom)],
        radius=envelope_radius,
        fill=ENVELOPE_COLOR,
        outline=BG_COLOR,
        width=2
    )
    
    # 信封折线
    fold_points = [
        (envelope_left, envelope_top),
        (center, envelope_top + int(envelope_height * 0.55)),
        (envelope_right, envelope_top)
    ]
    line_width = max(1, ICON_SIZE // 64)
    draw.line(fold_points, fill=BG_COLOR, width=line_width, joint="round")
    
    # 气泡尾巴
    bubble_tail = [
        (envelope_right - int(ICON_SIZE * 0.06), envelope_bottom - int(ICON_SIZE * 0.04)),
        (envelope_right + int(ICON_SIZE * 0.08), envelope_bottom + int(ICON_SIZE * 0.06)),
        (envelope_right - int(ICON_SIZE * 0.01), envelope_bottom + int(ICON_SIZE * 0.02)),
    ]
    draw.polygon(bubble_tail, fill=ENVELOPE_COLOR)
    
    # 闪电
    lightning_top = envelope_top + int(envelope_height * 0.25)
    lightning_bottom = envelope_bottom - int(envelope_height * 0.25)
    lightning_points = [
        (center, lightning_top),
        (center - int(ICON_SIZE * 0.06), center),
        (center, center),
        (center - int(ICON_SIZE * 0.02), lightning_bottom),
        (center + int(ICON_SIZE * 0.04), center - int(ICON_SIZE * 0.02)),
        (center + int(ICON_SIZE * 0.02), center),
        (center + int(ICON_SIZE * 0.06), lightning_top + int(ICON_SIZE * 0.02)),
    ]
    draw.polygon(lightning_points, fill=LIGHTNING_COLOR)
    
    # 高光
    highlight_ellipse = [
        (margin + int(ICON_SIZE * 0.05), margin + int(ICON_SIZE * 0.05)),
        (margin + int(ICON_SIZE * 0.25), margin + int(ICON_SIZE * 0.15))
    ]
    draw.ellipse(highlight_ellipse, fill=(255, 255, 255, 60))
    
    img.save(OUTPUT_FILE, "PNG")
    print(f"[完成] 图标已生成: {OUTPUT_FILE}")
    print(f"       尺寸: {ICON_SIZE}x{ICON_SIZE}")
    
    return OUTPUT_FILE


def create_multi_sizes():
    """生成多个尺寸的图标"""
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        margin = int(ICON_SIZE * 0.08)
        center = ICON_SIZE // 2
        
        bg_radius = int(ICON_SIZE * 0.2)
        draw.rounded_rectangle(
            [(margin, margin), (ICON_SIZE - margin, ICON_SIZE - margin)],
            radius=bg_radius,
            fill=BG_COLOR
        )
        
        envelope_width = int(ICON_SIZE * 0.5)
        envelope_height = int(ICON_SIZE * 0.35)
        envelope_left = center - envelope_width // 2
        envelope_top = center - envelope_height // 2 + int(ICON_SIZE * 0.03)
        envelope_right = envelope_left + envelope_width
        envelope_bottom = envelope_top + envelope_height
        
        draw.rounded_rectangle(
            [(envelope_left, envelope_top), (envelope_right, envelope_bottom)],
            radius=int(ICON_SIZE * 0.03),
            fill="white"
        )
        
        fold_points = [
            (envelope_left, envelope_top),
            (center, envelope_top + int(envelope_height * 0.55)),
            (envelope_right, envelope_top)
        ]
        draw.line(fold_points, fill=BG_COLOR, width=max(1, ICON_SIZE // 64), joint="round")
        
        lightning_top = envelope_top + int(envelope_height * 0.25)
        lightning_bottom = envelope_bottom - int(envelope_height * 0.25)
        lightning_points = [
            (center, lightning_top),
            (center - int(ICON_SIZE * 0.06), center),
            (center, center),
            (center - int(ICON_SIZE * 0.02), lightning_bottom),
            (center + int(ICON_SIZE * 0.04), center - int(ICON_SIZE * 0.02)),
            (center + int(ICON_SIZE * 0.02), center),
            (center + int(ICON_SIZE * 0.06), lightning_top + int(ICON_SIZE * 0.02)),
        ]
        draw.polygon(lightning_points, fill="#FFD700")
        
        resized = img.resize((size, size), RESAMPLE_FILTER)
        images.append(resized)
        resized.save(f"icon_{size}x{size}.png")
        print(f"生成: icon_{size}x{size}.png")
    
    ico_path = "app_icon.ico"
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print(f"[完成] ICO 图标已生成: {ico_path}")
    return ico_path


# ============================================================================
# 主程序
# ============================================================================
def main():
    print("=" * 50)
    print("AI 邮件客户端图标生成器")
    print("=" * 50)
    
    create_icon()
    
    print("\n是否生成多尺寸图标（用于 Windows exe 打包）？")
    choice = input("输入 y 生成，其他跳过: ").strip().lower()
    
    if choice == 'y':
        create_multi_sizes()
    
    print("\n[完成] 所有图标已生成！")


if __name__ == "__main__":
    main()