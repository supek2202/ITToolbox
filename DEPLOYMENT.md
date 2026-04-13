# IT工具箱 部署说明

## 项目概述

IT工具箱 是一个网络设备巡检工具，支持多厂商设备（华为、H3C、Cisco、锐捷、Juniper、浪潮等）的自动化巡检。

**主要功能：**
- 自动设备发现（SNMP）
- SSH/Telnet 连接
- 特权模式自动进入
- 批量巡检执行
- 结果导出（HTML/CSV）
- macOS 原生应用打包

**技术栈：**
- Python 3.11
- Tkinter GUI
- netmiko（网络连接）
- PyInstaller（打包）

---

## 文件结构

```
network_inspector/
├── it_toolbox.py      # 主程序（79KB）
├── commands.json         # 巡检命令库（40KB，106条命令）
├── IT工具箱.spec     # PyInstaller 配置
├── create_icon.py        # 图标生成脚本
├── .github/
│   └── workflows/
│       └── build.yml     # Windows CI 工作流
├── SPEC.md               # 技术规格文档
├── requirements.txt      # Python 依赖
└── .gitignore           # Git 忽略规则
```

---

## GitHub 仓库

**地址：** https://github.com/supek2202/IT工具箱

**当前状态：**
- 主分支：main
- 最新提交：f283ab4b6ffe
- 已推送文件：
  - ✅ it_toolbox.py
  - ✅ commands.json
  - ✅ IT工具箱.spec
  - ✅ create_icon.py
  - ✅ .gitignore
  - ✅ SPEC.md
  - ✅ requirements.txt
  - ⚠️ .github/workflows/build.yml（需要手动更新，见下文）

---

## macOS 本地构建

### 环境要求
- macOS 10.15+
- Python 3.11
- PyInstaller 6.x

### 构建步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 生成图标（首次构建）
python create_icon.py

# 3. 打包应用
pyinstaller IT工具箱.spec

# 4. 运行
open dist/IT工具箱.app
```

### 输出位置
- 应用包：`dist/IT工具箱.app`
- 构建缓存：`build/`

---

## Windows 构建（GitHub Actions）

### 工作流说明

项目配置了 GitHub Actions 自动构建 Windows 版本。

**触发条件：**
- 推送到 main 分支
- 手动触发（workflow_dispatch）

**构建流程：**
1. 检出代码
2. 安装 Python 3.11
3. 安装依赖（pyinstaller, netmiko, paramiko, pillow）
4. PyInstaller 打包
5. 上传构建产物（保留 30 天）

### 下载 Windows 版本

1. 打开 https://github.com/supek2202/IT工具箱/actions
2. 点击最新的成功构建
3. 在 **Artifacts** 区域下载 `IT工具箱-Windows.zip`
4. 解压后运行 `IT工具箱.exe`

### ⚠️ 重要：手动更新 workflow 文件

由于 GitHub API 对 `.github/workflows/` 路径的特殊限制，workflow 文件无法通过 API 自动推送。

**手动更新步骤：**

1. 打开 https://github.com/supek2202/IT工具箱/edit/main/.github/workflows/build.yml

2. 粘贴以下内容：

```yaml
name: Build Windows EXE

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Python deps
        run: |
          python -m pip install --upgrade pip
          pip install pyinstaller netmiko paramiko pillow
          pip list

      - name: Build with PyInstaller
        run: |
          pyinstaller --noconfirm --onedir --windowed ^
            --name IT工具箱 ^
            --add-data "commands.json;." ^
            --hidden-import=netmiko ^
            --hidden-import=paramiko ^
            --hidden-import=PIL ^
            it_toolbox.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: IT工具箱-Windows
          path: dist/IT工具箱/
          retention-days: 30
```

3. 点击 **Commit changes**

4. 提交后会自动触发构建

---

## 巡检命令库

### 当前状态

`commands.json` 包含 **106 条命令**，覆盖以下厂商：

| 厂商 | 设备类型 | 命令数量 |
|------|---------|---------|
| 华为 (Huawei) | 交换机/路由器/防火墙 | 12+ |
| H3C | 交换机/路由器/防火墙 | 12+ |
| Cisco | 交换机/路由器 | 6+ |
| 锐捷 (Ruijie) | 交换机/路由器 | 6+ |
| Juniper | 路由器 | 4+ |
| 浪潮 (Inspur) | 交换机/路由器 | 12+ |

### 命令类型

**基础信息：**
- 版本信息（show version / display version）
- 系统时间（show clock / display clock）
- 设备配置（show running-config）

**状态检查：**
- CPU 使用率（show cpu / display cpu）
- 内存使用（show memory / display memory）
- 接口状态（show interface / display interface）
- ARP 表（show arp / display arp）
- MAC 地址表（show mac-address / display mac-address）

**高级功能：**
- VRRP 状态
- IRF/堆叠状态
- M-LAG 状态
- 邻居发现（LLDP/CDP）
- 路由表（show ip route）
- 日志信息

### 待完善项

当前命令库存在以下问题：
1. 部分厂商命令重复（show version 在多个厂商中重复）
2. 缺少某些高级功能命令（IRF、M-LAG 等）
3. 命令分类不够清晰

**建议改进：**
- 去除重复命令
- 补充 IRF/堆叠/M-LAG 命令
- 添加命令分类标签

---

## 开发历程（技术笔记）

### 已解决问题

**1. Telnet 连接问题**
- 问题：锐捷交换机 10.160.3.246 连接返回乱码（0xff 字节）
- 原因：设备只支持 Telnet，不支持 SSH
- 解决：协议选择联动端口（SSH→22，Telnet→23）

**2. 特权模式问题**
- 问题：防火墙/路由器需要特权模式才能执行巡检命令
- 解决：自动检测厂商类型并进入特权模式
  - Cisco/Ruijie：`enable`
  - Huawei/H3C：`system-view`

**3. UI 布局优化**
- 问题：原始布局不够紧凑
- 解决：2x2 网格布局
  - 左上：设备列表
  - 右上：设备详情
  - 左下：日志输出
  - 右下：巡检结果

**4. GitHub 推送问题**
- 问题：Git 网络被阻止，无法直接 push
- 解决：使用 GitHub API 逐文件推送
  - 简单路径文件：Contents API（成功）
  - `.github/workflows/` 路径：需要手动更新（API 限制）

### 未解决问题

**1. Workflow 文件自动更新**
- 问题：GitHub API 对 `.github/workflows/` 路径有特殊限制
- 临时方案：手动在 GitHub 网页编辑
- 长期方案：探索其他 CI/CD 方式或使用 GitHub App

**2. 新建 Blob 引用问题**
- 问题：通过 API 新建的 blob 无法立即在 tree 创建中引用
- 原因：可能是 GitHub API 的限制或时序问题
- 影响：无法通过 API 更新已存在的 `.github/` 路径文件

---

## 使用说明

### 添加设备

1. 点击 **"发现设备"** 按钮
2. 输入网段（如 192.168.1.0/24）
3. 输入 SNMP community（默认 public）
4. 等待扫描完成
5. 选择设备并添加凭据

### 手动添加设备

1. 点击 **"添加设备"** 按钮
2. 填写设备信息：
   - 类型：交换机/路由器/防火墙
   - 厂商：Huawei/H3C/Cisco/Ruijie/Juniper/Inspur
   - IP 地址
   - 协议：SSH/Telnet（联动端口）
   - 用户名/密码
   - 特权密码（如需要）
3. 点击 **"保存"**

### 执行巡检

1. 在设备列表选择目标设备
2. 点击 **"开始巡检"**
3. 等待巡检完成
4. 查看巡检结果
5. 点击 **"导出巡检信息"** 保存报告

### 测试连接

在添加设备后，点击 **"测试连接"** 验证：
- 网络连通性
- 认证信息
- 特权模式（如需要）

---

## 依赖清单

```
# 网络连接
netmiko>=4.0.0
paramiko>=3.0.0

# SNMP 设备发现
pysnmp>=5.0.0

# 图形界面
# Tkinter (Python 内置)

# 图标生成
Pillow>=10.0.0

# 打包工具
pyinstaller>=6.0.0
```

---

## 版本信息

- **版本：** 1.0
- **更新日期：** 2026-04-13
- **维护状态：** 活跃开发中

---

## 联系方式

如有问题，请通过以下方式反馈：
- GitHub Issues：https://github.com/supek2202/IT工具箱/issues
- 项目文档：见 SPEC.md

---

*本文档由 OpenClaw AI 自动生成，记录了 IT工具箱 项目的部署和开发历程。*
