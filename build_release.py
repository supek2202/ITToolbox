#!/usr/bin/env python3
"""
IT工具箱 - 跨平台打包脚本
生成可直接运行的绿色版程序包（无需安装）

用法：
    python build_release.py              # 默认单文件模式
    python build_release.py --onedir     # 文件夹模式（启动更快）
    python build_release.py --onefile    # 单文件模式（便携）
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.absolute()
DIST_DIR = PROJECT_DIR / "dist"
RELEASE_DIR = PROJECT_DIR / "release"

# 应用信息
APP_NAME = "IT工具箱"
APP_NAME_EN = "ITToolbox"
VERSION = "1.0.0"

def clean():
    """清理构建目录"""
    print("🧹 清理构建目录...")
    dirs = ["build", "dist", "release", "__pycache__"]
    for d in dirs:
        p = PROJECT_DIR / d
        if p.exists():
            shutil.rmtree(p)
            print(f"   删除: {p}")
    
    # 删除 spec 文件（会重新生成）
    for spec in PROJECT_DIR.glob("*.spec"):
        spec.unlink()
        print(f"   删除: {spec}")

def build_macos(mode="onefile"):
    """macOS 打包"""
    print(f"\n📦 macOS 打包 (模式: {mode})...")
    
    # PyInstaller 参数
    args = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",  # 无控制台窗口
        f"--name={APP_NAME}",
        f"--add-data=commands.json:.",
        "--hidden-import=netmiko",
        "--hidden-import=paramiko",
        "--hidden-import=PIL",
        "--hidden-import=PIL._tkinter_finder",
        "--osx-bundle-identifier=com.ittoolbox.app",
    ]
    
    if mode == "onefile":
        args.append("--onefile")
    else:
        args.append("--onedir")
    
    args.append("it_toolbox.py")
    
    # 执行打包
    print(f"   执行: {' '.join(args)}")
    result = subprocess.run(args, cwd=PROJECT_DIR)
    
    if result.returncode != 0:
        print("❌ 打包失败")
        return False
    
    # 创建发布包
    RELEASE_DIR.mkdir(exist_ok=True)
    
    if mode == "onefile":
        # 单文件：直接复制
        src = DIST_DIR / f"{APP_NAME}"
        dst = RELEASE_DIR / f"{APP_NAME}_macOS"
        if src.exists():
            shutil.copy2(src, dst)
            print(f"✅ 单文件已生成: {dst}")
    else:
        # 文件夹：打包 .app
        src = DIST_DIR / f"{APP_NAME}.app"
        dst = RELEASE_DIR / f"{APP_NAME}.app"
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"✅ .app 已生成: {dst}")
    
    return True

def build_windows(mode="onefile"):
    """Windows 打包（在 Windows 上运行）"""
    print(f"\n📦 Windows 打包 (模式: {mode})...")
    
    # PyInstaller 参数
    args = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",  # 无控制台窗口
        f"--name={APP_NAME}",
        f"--add-data=commands.json;.",  # Windows 用分号
        "--hidden-import=netmiko",
        "--hidden-import=paramiko",
        "--hidden-import=PIL",
    ]
    
    if mode == "onefile":
        args.append("--onefile")
    else:
        args.append("--onedir")
    
    args.append("it_toolbox.py")
    
    # 执行打包
    print(f"   执行: {' '.join(args)}")
    result = subprocess.run(args, cwd=PROJECT_DIR)
    
    if result.returncode != 0:
        print("❌ 打包失败")
        return False
    
    # 创建发布包
    RELEASE_DIR.mkdir(exist_ok=True)
    
    if mode == "onefile":
        src = DIST_DIR / f"{APP_NAME}.exe"
        dst = RELEASE_DIR / f"{APP_NAME}_Windows.exe"
        if src.exists():
            shutil.copy2(src, dst)
            print(f"✅ 单文件已生成: {dst}")
    else:
        src = DIST_DIR / APP_NAME
        dst = RELEASE_DIR / f"{APP_NAME}_Windows"
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"✅ 文件夹已生成: {dst}")
    
    return True

def create_dmg():
    """创建 macOS DMG 安装包"""
    print("\n📀 创建 DMG...")
    
    app_path = RELEASE_DIR / f"{APP_NAME}.app"
    dmg_path = RELEASE_DIR / f"{APP_NAME}_{VERSION}.dmg"
    
    if not app_path.exists():
        print("❌ .app 不存在，请先打包")
        return False
    
    # 使用 hdiutil 创建 DMG
    cmd = [
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", str(app_path),
        "-ov", "-format", "UDZO",
        str(dmg_path)
    ]
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print(f"✅ DMG 已生成: {dmg_path}")
        return True
    else:
        print("❌ DMG 创建失败")
        return False

def create_zip():
    """创建 ZIP 发布包"""
    print("\n📦 创建 ZIP 发布包...")
    
    import zipfile
    
    # macOS: 打包 .app
    app_path = RELEASE_DIR / f"{APP_NAME}.app"
    if app_path.exists():
        zip_path = RELEASE_DIR / f"{APP_NAME}_macOS_{VERSION}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(app_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(RELEASE_DIR)
                    zf.write(file_path, arcname)
        print(f"✅ macOS ZIP: {zip_path}")
    
    # Windows: 打包文件夹
    win_dir = RELEASE_DIR / f"{APP_NAME}_Windows"
    if win_dir.exists():
        zip_path = RELEASE_DIR / f"{APP_NAME}_Windows_{VERSION}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(win_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(RELEASE_DIR)
                    zf.write(file_path, arcname)
        print(f"✅ Windows ZIP: {zip_path}")
    
    # Windows 单文件
    win_exe = RELEASE_DIR / f"{APP_NAME}_Windows.exe"
    if win_exe.exists():
        zip_path = RELEASE_DIR / f"{APP_NAME}_Windows_{VERSION}_Portable.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(win_exe, f"{APP_NAME}.exe")
        print(f"✅ Windows 便携版 ZIP: {zip_path}")

def main():
    # 解析参数
    mode = "onefile"
    if "--onedir" in sys.argv:
        mode = "onedir"
    elif "--onefile" in sys.argv:
        mode = "onefile"
    
    print("=" * 50)
    print(f"IT工具箱 v{VERSION} - 打包脚本")
    print(f"模式: {mode}")
    print(f"平台: {platform.system()}")
    print("=" * 50)
    
    # 检查依赖
    try:
        import netmiko
        import PIL
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("   请运行: pip install netmiko pillow")
        return 1
    
    # 清理
    clean()
    
    # 打包
    system = platform.system()
    if system == "Darwin":
        if not build_macos(mode):
            return 1
        # 创建 DMG 或 ZIP
        if mode == "onedir":
            create_dmg()
        else:
            create_zip()
    elif system == "Windows":
        if not build_windows(mode):
            return 1
        create_zip()
    else:
        print(f"❌ 不支持的操作系统: {system}")
        return 1
    
    # 显示结果
    print("\n" + "=" * 50)
    print("🎉 打包完成！")
    print(f"   发布目录: {RELEASE_DIR}")
    print("\n   文件列表:")
    for f in RELEASE_DIR.glob("*"):
        size = f.stat().st_size / (1024 * 1024)
        print(f"   - {f.name} ({size:.1f} MB)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
