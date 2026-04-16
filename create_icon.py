#!/usr/bin/env python3
"""生成 IT工具箱 应用图标 🧰 - 工具箱图标"""
from PIL import Image, ImageDraw, ImageFont
import os, subprocess, tempfile

OUTPUT = "/Users/mac/.qclaw/workspace/network_inspector/dist/IT工具箱.app/Contents/Resources/icon-windowed.icns"

def get_font(size):
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
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

def draw_toolbox(img_size, bg_color, body_color, handle_color, accent_color):
    """绘制工具箱图标"""
    s = img_size
    cx = s // 2
    
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # ===== 圆角矩形背景 =====
    r = int(s * 0.18)
    draw.rounded_rectangle([0, 0, s-1, s-1], radius=r, fill=bg_color)
    
    # ===== 工具箱主体 =====
    box_top = int(s * 0.38)
    box_bottom = int(s * 0.88)
    box_left = int(s * 0.12)
    box_right = int(s * 0.88)
    box_cx = cx
    box_cy = (box_top + box_bottom) // 2
    box_h = box_bottom - box_top
    box_w = box_right - box_left
    
    # 主体矩形
    body_r = int(s * 0.08)
    draw.rounded_rectangle([box_left, box_top, box_right, box_bottom], 
                           radius=body_r, fill=body_color)
    
    # 主体顶部高光
    highlight_y1 = box_top + int(s * 0.03)
    highlight_y2 = box_top + int(s * 0.12)
    draw.rounded_rectangle([box_left + int(s*0.02), highlight_y1, 
                             box_right - int(s*0.02), highlight_y2],
                            radius=int(s*0.04), fill=(255,255,255,60))
    
    # ===== 箱盖（顶部突出的部分）=====
    lid_left = int(s * 0.08)
    lid_right = int(s * 0.92)
    lid_top = int(s * 0.20)
    lid_bottom = box_top + int(s * 0.06)
    lid_cy = (lid_top + lid_bottom) // 2
    lid_h = lid_bottom - lid_top
    lid_w = lid_right - lid_left
    
    draw.rounded_rectangle([lid_left, lid_top, lid_right, lid_bottom],
                           radius=int(s*0.06), fill=body_color)
    
    # 箱盖顶部高光
    lid_hl_y1 = lid_top + int(s * 0.02)
    lid_hl_y2 = lid_top + int(s * 0.08)
    draw.rounded_rectangle([lid_left + int(s*0.02), lid_hl_y1,
                              lid_right - int(s*0.02), lid_hl_y2],
                             radius=int(s*0.03), fill=(255,255,255,60))
    
    # ===== 把手 =====
    handle_w = int(s * 0.22)
    handle_h = int(s * 0.14)
    handle_left = cx - handle_w // 2
    handle_right = cx + handle_w // 2
    handle_top = int(s * 0.05)
    handle_bottom = lid_top + int(s * 0.02)
    
    # 把手连接件
    conn_h = int(s * 0.04)
    draw.rounded_rectangle([handle_left + int(s*0.04), lid_top - conn_h,
                              handle_right - int(s*0.04), lid_top],
                             radius=int(s*0.02), fill=handle_color)
    draw.rounded_rectangle([handle_left + int(s*0.04), handle_top,
                              handle_right - int(s*0.04), handle_top + conn_h],
                             radius=int(s*0.02), fill=handle_color)
    
    # 把手主体（拱形）
    handle_arc_top = handle_top + int(s * 0.02)
    handle_arc_bottom = lid_top - int(s * 0.02)
    draw.rounded_rectangle([handle_left, handle_arc_top,
                              handle_right, handle_arc_bottom],
                             radius=int(s*0.08), fill=handle_color)
    
    # ===== 锁扣 =====
    lock_w = int(s * 0.08)
    lock_h = int(s * 0.06)
    lock_cx = cx
    lock_cy = (box_top + lid_bottom) // 2 + int(s * 0.02)
    
    draw.rounded_rectangle([lock_cx - lock_w//2, lock_cy - lock_h//2,
                              lock_cx + lock_w//2, lock_cy + lock_h//2],
                             radius=int(s*0.02), fill=accent_color)
    
    # 锁孔
    keyhole_w = int(s * 0.02)
    keyhole_h = int(s * 0.03)
    draw.ellipse([lock_cx - keyhole_w//2, lock_cy - int(s*0.015),
                   lock_cx + keyhole_w//2, lock_cy + int(s*0.015)],
                  fill=(0,0,0,80))
    
    # ===== 侧面装饰线 =====
    line_y = box_cy + int(box_h * 0.15)
    line_w = int(s * 0.08)
    draw.rounded_rectangle([box_left + int(s*0.04), line_y,
                              box_left + int(s*0.04) + line_w, line_y + int(s*0.025)],
                             radius=int(s*0.01), fill=accent_color)
    
    # ===== 底部支脚 =====
    foot_h = int(s * 0.025)
    foot_w = int(s * 0.06)
    draw.rounded_rectangle([box_left + int(s*0.04), box_bottom - foot_h,
                              box_left + int(s*0.04) + foot_w, box_bottom],
                             radius=int(s*0.01), fill=(0,0,0,40))
    draw.rounded_rectangle([box_right - int(s*0.04) - foot_w, box_bottom - foot_h,
                              box_right - int(s*0.04), box_bottom],
                             radius=int(s*0.01), fill=(0,0,0,40))
    
    # ===== IT 文字 =====
    font_size = max(14, int(s * 0.24))
    font = get_font(font_size)
    text = "IT"
    
    try:
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except:
        tw = font_size * 1.2
        th = font_size
    
    tx = cx - tw // 2
    ty = box_cy - th // 2 + int(s * 0.04)
    
    # 文字阴影
    draw.text((tx + 1, ty + 1), text, font=font, fill=(0,0,0,50))
    # 文字主体
    draw.text((tx, ty), text, font=font, fill=(255,255,255))
    
    return img

def create_icon(size):
    """创建单个尺寸的图标"""
    # 配色方案：蓝色工具箱
    bg = (45, 90, 160)        # 深蓝背景
    body = (65, 130, 200)     # 箱体蓝
    handle = (85, 155, 230)   # 把手亮蓝
    accent = (255, 195, 50)   # 金黄色锁扣
    
    return draw_toolbox(size, bg, body, handle, accent)

def create_icns(output_path):
    """生成 ICNS 文件"""
    tmpdir = tempfile.mkdtemp()
    iconset = f"{tmpdir}/icon.iconset"
    os.makedirs(iconset)
    
    # 生成 iconset
    sizes = [(16, 1), (32, 1), (64, 1), (128, 1), (256, 2), (512, 2)]
    for sz, scale in sizes:
        img = create_icon(sz * scale)
        img.save(f"{iconset}/icon_{sz}x{sz}.png")
        if scale == 2:
            img2x = create_icon(sz * 2)
            img2x.save(f"{iconset}/icon_{sz}x{sz}@2.png")
    
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', output_path], 
                     capture_output=True, check=True)
        size = os.path.getsize(output_path)
        print(f"✅ 图标已生成: {output_path}")
        print(f"   大小: {size/1024:.1f} KB")
    except subprocess.CalledProcessError as e:
        print(f"iconutil 失败: {e.stderr.decode() if e.stderr else str(e)}")
        # fallback: 保存 PNG
        img512 = create_icon(512)
        png_path = os.path.dirname(output_path) + "/icon.png"
        img512.save(png_path)
        print(f"✅ 已生成 PNG: {png_path}")

if __name__ == "__main__":
    create_icns(OUTPUT)
