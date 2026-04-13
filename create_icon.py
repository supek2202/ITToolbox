#!/usr/bin/env python3
"""生成 NetInspector 应用图标 🦞 - 白底小龙虾钳子"""
from PIL import Image, ImageDraw, ImageFont
import os, subprocess, tempfile

OUTPUT = "/Users/mac/.qclaw/workspace/network_inspector/dist/NetInspector.app/Contents/Resources/icon-windowed.icns"

def get_font(size):
    """获取字体"""
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/FontsSupplemental/Arial.ttf",
        "/System/Library/Fonts/Arial.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                continue
    return ImageFont.load_default()

def draw_claw(draw, cx, cy, size, color):
    """画小龙虾钳子"""
    s = size * 0.4  # 钳子大小
    
    # 钳子大臂 (椭圆形)
    arm_w = s * 0.35
    arm_h = s * 0.8
    draw.ellipse([cx - arm_w, cy - arm_h, cx + arm_w, cy + arm_h], fill=color)
    
    # 钳子小臂 (倾斜的椭圆)
    small_arm_w = s * 0.25
    small_arm_h = s * 0.6
    # 上半部分
    draw.ellipse([cx + s*0.1 - small_arm_w, cy - arm_h - small_arm_h*0.5,
                  cx + s*0.1 + small_arm_w, cy - arm_h + small_arm_h*0.3], fill=color)
    # 下半部分
    draw.ellipse([cx - s*0.3 - small_arm_w, cy - arm_h*0.3 - small_arm_h*0.5,
                  cx - s*0.3 + small_arm_w, cy - arm_h*0.3 + small_arm_h*0.5], fill=color)
    
    # 锯齿 (3个三角形)
    lw = max(2, int(size * 0.025))
    for i in range(3):
        y_offset = cy - arm_h + s * 0.2 + i * s * 0.25
        tri_size = s * 0.2
        # 左侧锯齿
        draw.polygon([(cx - s*0.15, y_offset - tri_size), 
                      (cx - s*0.15 - tri_size, y_offset + tri_size*0.5),
                      (cx - s*0.15 + tri_size*0.5, y_offset + tri_size*0.5)], fill=color)
        # 右侧锯齿
        draw.polygon([(cx + s*0.35, y_offset - tri_size), 
                      (cx + s*0.35 + tri_size, y_offset + tri_size*0.5),
                      (cx + s*0.35 - tri_size*0.5, y_offset + tri_size*0.5)], fill=color)

def create_icon(size):
    """创建单个尺寸的图标"""
    bg = (255, 255, 255)   # 白底
    fg = (220, 80, 60)     # 龙虾红 #DC503C
    
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 圆角矩形背景 (白色)
    r = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=r, fill=bg, outline=fg, width=max(2, int(size*0.02)))
    
    # 画小龙虾钳子 (偏左)
    claw_cx = size // 2 - int(size * 0.08)
    claw_cy = size // 2 + int(size * 0.05)
    draw_claw(draw, claw_cx, claw_cy, size, fg)
    
    # 画第二个钳子 (镜像，偏右)
    claw_cx2 = size // 2 + int(size * 0.08)
    # 翻转绘制 - 用另一个函数
    draw_claw_mirrored(draw, claw_cx2, claw_cy, size, fg)
    
    # NI 文字 (红色)
    font_size = max(12, int(size * 0.22))
    font = get_font(font_size)
    
    text = "NI"
    ty = int(size * 0.65)
    
    # 文字居中
    try:
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        tx = (size - tw) // 2
    except:
        tx = size // 2 - font_size // 2
    
    draw.text((tx, ty), text, font=font, fill=fg)
    
    return img

def draw_claw_mirrored(draw, cx, cy, size, color):
    """画小龙虾钳子 (镜像)"""
    s = size * 0.4
    
    # 钳子大臂
    arm_w = s * 0.35
    arm_h = s * 0.8
    draw.ellipse([cx - arm_w, cy - arm_h, cx + arm_w, cy + arm_h], fill=color)
    
    # 钳子小臂 (镜像)
    small_arm_w = s * 0.25
    small_arm_h = s * 0.6
    draw.ellipse([cx - s*0.1 - small_arm_w, cy - arm_h - small_arm_h*0.5,
                  cx - s*0.1 + small_arm_w, cy - arm_h + small_arm_h*0.3], fill=color)
    draw.ellipse([cx + s*0.3 - small_arm_w, cy - arm_h*0.3 - small_arm_h*0.5,
                  cx + s*0.3 + small_arm_w, cy - arm_h*0.3 + small_arm_h*0.5], fill=color)
    
    # 锯齿 (镜像)
    for i in range(3):
        y_offset = cy - arm_h + s * 0.2 + i * s * 0.25
        tri_size = s * 0.2
        draw.polygon([(cx - s*0.35, y_offset - tri_size), 
                      (cx - s*0.35 - tri_size, y_offset + tri_size*0.5),
                      (cx - s*0.35 + tri_size*0.5, y_offset + tri_size*0.5)], fill=color)
        draw.polygon([(cx + s*0.15, y_offset - tri_size), 
                      (cx + s*0.15 + tri_size, y_offset + tri_size*0.5),
                      (cx + s*0.15 - tri_size*0.5, y_offset + tri_size*0.5)], fill=color)

def create_icns(output_path):
    """生成 ICNS 文件"""
    tmpdir = tempfile.mkdtemp()
    iconset = f"{tmpdir}/icon.iconset"
    os.makedirs(iconset)
    
    # 生成 iconset
    for sz in [16, 32, 64, 128, 256, 512]:
        img = create_icon(sz)
        img.save(f"{iconset}/icon_{sz}x{sz}.png")
        # Retina 2x
        img2x = create_icon(sz * 2)
        img2x.save(f"{iconset}/icon_{sz}x{sz}@2.png")
    
    try:
        subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', output_path], 
                     capture_output=True, check=True)
        size = os.path.getsize(output_path)
        print(f"✅ 图标已生成: {output_path}")
        print(f"   大小: {size/1024:.1f} KB")
    except subprocess.CalledProcessError as e:
        print(f"iconutil 失败: {e.stderr.decode() if e.stderr else str(e)}")
        img512 = create_icon(512)
        png_path = output_path.replace('.icns', '.png')
        img512.save(png_path)
        print(f"✅ 已生成 PNG: {png_path}")

if __name__ == "__main__":
    create_icns(OUTPUT)
