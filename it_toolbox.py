#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IT工具箱 v1.0 - 网络设备巡检工具
支持路由器、交换机、防火墙等网络设备的自动发现、连接、巡检
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import os
import sys
import socket
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# 尝试导入netmiko，如果失败则使用paramiko
try:
    from netmiko import ConnectHandler
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False
    try:
        import paramiko
        PARAMIKO_AVAILABLE = True
    except ImportError:
        PARAMIKO_AVAILABLE = False


class DeviceInspectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IT工具箱 v1.0 - 网络设备巡检工具")
        self.root.geometry("740x520")
        self.root.resizable(False, False)

        # 数据文件路径 - 支持打包后路径
        try:
            if getattr(sys, 'frozen', False):
                # 打包后的可执行文件
                self.base_dir = os.path.dirname(sys.executable)
            else:
                # 开发环境
                self.base_dir = os.path.dirname(os.path.abspath(__file__))
        except:
            # 如果__file__未定义，使用当前工作目录
            self.base_dir = os.getcwd()

        # macOS .app 包的特殊处理
        if 'IT工具箱.app' in self.base_dir:
            # 在 Resources 目录中查找
            resources_dir = os.path.join(self.base_dir, '..', 'Resources')
            if os.path.exists(os.path.join(resources_dir, 'commands.json')):
                self.commands_file = os.path.join(resources_dir, 'commands.json')
            else:
                self.commands_file = os.path.join(self.base_dir, "commands.json")
        else:
            self.commands_file = os.path.join(self.base_dir, "commands.json")

        self.devices_file = os.path.join(self.base_dir, "devices.json")

        # 加载数据
        self.devices = self.load_devices()
        self.commands_data = self.load_commands()

        # 扫描相关
        self.scan_results = []
        self.scan_running = False
        self.inspect_running = False

        # 初始化UI
        self.init_ui()

        # 刷新设备列表
        self.refresh_device_list()

    def load_devices(self):
        """加载设备列表"""
        if os.path.exists(self.devices_file):
            try:
                with open(self.devices_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_devices(self):
        """保存设备列表"""
        with open(self.devices_file, 'w', encoding='utf-8') as f:
            json.dump(self.devices, f, ensure_ascii=False, indent=2)

    def load_commands(self):
        """加载巡检命令库"""
        if os.path.exists(self.commands_file):
            try:
                with open(self.commands_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"commands": [], "vendors": [], "device_types": []}
        return {"commands": [], "vendors": [], "device_types": []}

    def init_ui(self):
        """初始化UI - 紧凑布局 740x520
        布局: 设备列表 | 设备详情
             日志输出 | 巡检结果
        """
        # 顶部工具栏 - 扁平按钮
        toolbar = tk.Frame(self.root, bg="#f0f0f0")
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=1)

        # 工具下拉菜单（合并发现设备、子网扫描、批量Ping）
        tool_menu = tk.Menubutton(toolbar, text="🔧 工具 ▼", relief=tk.FLAT, bg="#f0f0f0")
        tool_menu.pack(side=tk.LEFT, padx=2)
        tool_menu.menu = tk.Menu(tool_menu, tearoff=0)
        tool_menu["menu"] = tool_menu.menu
        tool_menu.menu.add_command(label="🔍 发现设备", command=self.show_discovery_dialog)
        tool_menu.menu.add_command(label="📡 子网扫描", command=self.show_subnet_scan_dialog)
        tool_menu.menu.add_command(label="📶 批量Ping", command=self.show_batch_ping_dialog)

        tk.Button(toolbar, text="➕ 添加设备", relief=tk.FLAT, bg="#f0f0f0",
                  command=self.show_add_device_dialog).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="▶️ 执行巡检", relief=tk.FLAT, bg="#f0f0f0",
                  command=self.run_inspection).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="📤 导出巡检信息", relief=tk.FLAT, bg="#f0f0f0",
                  command=self.export_report).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="📝 命令管理", relief=tk.FLAT, bg="#f0f0f0",
                  command=self.show_commands_manager).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="🔄 刷新", relief=tk.FLAT, bg="#f0f0f0",
                  command=self.refresh_device_list).pack(side=tk.LEFT, padx=2)

        # 主内容区 - 2x2网格布局
        # 上排: 设备列表 | 设备详情
        # 下排: 日志输出  | 巡检结果
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=1)

        # 上排容器
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True)

        # 左上 - 设备列表
        list_frame = tk.LabelFrame(top_frame, text="设备列表", padx=2, pady=2)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2), pady=(0, 1))

        columns = ("序号", "类型", "厂商", "IP", "协议端口", "状态")
        self.device_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=7)

        self.device_tree.heading("序号", text="#")
        self.device_tree.heading("类型", text="类型")
        self.device_tree.heading("厂商", text="厂商")
        self.device_tree.heading("IP", text="IP地址")
        self.device_tree.heading("协议端口", text="协议/端口")
        self.device_tree.heading("状态", text="状态")

        self.device_tree.column("序号", width=30, anchor="center")
        self.device_tree.column("类型", width=60, anchor="center")
        self.device_tree.column("厂商", width=60, anchor="center")
        self.device_tree.column("IP", width=100, anchor="center")
        self.device_tree.column("协议端口", width=70, anchor="center")
        self.device_tree.column("状态", width=50, anchor="center")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=vsb.set)
        self.device_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.device_tree.bind("<Double-1>", self.on_device_double_click)
        self.device_tree.bind("<Button-3>", self.show_device_context_menu)

        # 右上 - 设备详情（每个字段一行）
        detail_frame = tk.LabelFrame(top_frame, text="设备详情", padx=2, pady=2)
        detail_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0), pady=(0, 1))

        form_frame = tk.Frame(detail_frame)
        form_frame.pack(fill=tk.X)

        # 类型
        tk.Label(form_frame, text="类型:").grid(row=0, column=0, sticky=tk.W, padx=2, pady=1)
        self.info_device_type = ttk.Combobox(form_frame, values=self.commands_data.get("device_types", []),
                                              state="readonly", width=15)
        self.info_device_type.grid(row=0, column=1, sticky=tk.W, padx=2, pady=1)

        # 厂商
        tk.Label(form_frame, text="厂商:").grid(row=1, column=0, sticky=tk.W, padx=2, pady=1)
        self.info_vendor = ttk.Combobox(form_frame, values=self.commands_data.get("vendors", []),
                                         state="readonly", width=15)
        self.info_vendor.grid(row=1, column=1, sticky=tk.W, padx=2, pady=1)

        # 型号
        tk.Label(form_frame, text="型号:").grid(row=2, column=0, sticky=tk.W, padx=2, pady=1)
        self.info_model = tk.Entry(form_frame, width=18)
        self.info_model.grid(row=2, column=1, sticky=tk.W, padx=2, pady=1)

        # IP
        tk.Label(form_frame, text="IP:").grid(row=3, column=0, sticky=tk.W, padx=2, pady=1)
        self.info_ip = tk.Entry(form_frame, width=18)
        self.info_ip.grid(row=3, column=1, sticky=tk.W, padx=2, pady=1)

        # 协议/端口（同行）
        tk.Label(form_frame, text="协议/端口:").grid(row=4, column=0, sticky=tk.W, padx=2, pady=1)
        proto_frame = tk.Frame(form_frame)
        proto_frame.grid(row=4, column=1, sticky=tk.W, padx=2, pady=1)
        self.info_protocol = ttk.Combobox(proto_frame, values=["SSH", "Telnet"], state="readonly", width=6)
        self.info_protocol.pack(side=tk.LEFT)
        tk.Label(proto_frame, text="/").pack(side=tk.LEFT, padx=2)
        self.info_port = tk.Entry(proto_frame, width=6)
        self.info_port.insert(0, "22")
        self.info_port.pack(side=tk.LEFT)

        def on_info_protocol_change(*args):
            if self.info_protocol.get() == "Telnet":
                self.info_port.delete(0, tk.END)
                self.info_port.insert(0, "23")
            else:
                self.info_port.delete(0, tk.END)
                self.info_port.insert(0, "22")
        self.info_protocol.bind("<<ComboboxSelected>>", on_info_protocol_change)

        # 用户
        tk.Label(form_frame, text="用户:").grid(row=5, column=0, sticky=tk.W, padx=2, pady=1)
        self.info_username = tk.Entry(form_frame, width=18)
        self.info_username.grid(row=5, column=1, sticky=tk.W, padx=2, pady=1)

        # 密码
        tk.Label(form_frame, text="密码:").grid(row=6, column=0, sticky=tk.W, padx=2, pady=1)
        self.info_password = tk.Entry(form_frame, show="*", width=18)
        self.info_password.grid(row=6, column=1, sticky=tk.W, padx=2, pady=1)

        # 特权密码
        tk.Label(form_frame, text="特权:").grid(row=7, column=0, sticky=tk.W, padx=2, pady=1)
        self.info_enable = tk.Entry(form_frame, show="*", width=18)
        self.info_enable.grid(row=7, column=1, sticky=tk.W, padx=2, pady=1)

        # 按钮行（单独一行）
        btn_frame = tk.Frame(detail_frame)
        btn_frame.pack(fill=tk.X, pady=2)
        tk.Button(btn_frame, text="保存", relief=tk.FLAT, bg="#e0e0e0",
                  command=self.save_device_info).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="删除", relief=tk.FLAT, bg="#e0e0e0",
                  command=self.delete_device).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="测试", relief=tk.FLAT, bg="#e0e0e0",
                  command=self.test_connection).pack(side=tk.LEFT, padx=2)

        # 下排容器
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(1, 0))

        # 左下 - 日志输出（缩小）
        log_frame = tk.LabelFrame(bottom_frame, text="日志输出", padx=2, pady=2)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2), pady=0)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=50, height=7)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 右下 - 巡检结果（放大）
        result_frame = tk.LabelFrame(bottom_frame, text="巡检结果", padx=2, pady=2)
        result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0), pady=0)

        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, width=40, height=10)
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # 底部版本号
        version_label = tk.Label(self.root, text="IT工具箱 v1.0 | 网络设备巡检工具",
                                  bg="#f0f0f0", fg="#666666", font=("Arial", 8))
        version_label.pack(side=tk.BOTTOM, fill=tk.X)

        # 当前选中的设备索引
        self.selected_device_index = None
        self.current_device_id = None

    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        # 移除 root.update() - 这会导致频繁UI刷新造成卡顿
        # 使用 after_idle 延迟更新，或者依赖主循环自然刷新

    def refresh_device_list(self):
        """刷新设备列表"""
        # 清空表格
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)

        # 填充数据
        for i, device in enumerate(self.devices):
            status = device.get("status", "未知")
            last_inspect = device.get("last_inspect", "未巡检")

            self.device_tree.insert("", tk.END, values=(
                i + 1,
                device.get("device_type", ""),
                device.get("vendor", ""),
                device.get("model", ""),
                device.get("ip", ""),
                f"{device.get('protocol', 'SSH')}/{device.get('port', '22')}",
                status,
                last_inspect
            ), tags=(device.get("id", ""),))

    def show_discovery_dialog(self):
        """显示设备发现对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("设备发现")
        dialog.geometry("580x560")
        dialog.transient(self.root)
        dialog.grab_set()

        # IP范围输入
        ttk.Label(dialog, text="IP范围或网段:").pack(pady=2)
        ip_entry = ttk.Entry(dialog, width=40)
        ip_entry.pack(pady=2)
        ttk.Label(dialog, text="例如: 192.168.1.1-254 或 192.168.1.0/24", font=("Arial", 9)).pack()

        # 端口选择
        ttk.Label(dialog, text="扫描端口:").pack(pady=2)
        ports_frame = ttk.Frame(dialog)
        ports_frame.pack(pady=2)

        port_vars = {}
        for port, name in [(22, "SSH"), (23, "Telnet"), (443, "HTTPS")]:
            var = tk.BooleanVar(value=True)
            port_vars[port] = var
            ttk.Checkbutton(ports_frame, text=f"{port} ({name})", variable=var).pack(side=tk.LEFT, padx=5)

        # 厂商识别
        ttk.Label(dialog, text="选项:").pack(pady=2)
        identify_vendor = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="自动识别厂商", variable=identify_vendor).pack()

        # 并发数
        ttk.Label(dialog, text="并发数:").pack(pady=2)
        threads_var = tk.IntVar(value=50)
        ttk.Spinbox(dialog, from_=10, to=200, textvariable=threads_var, width=10).pack()

        # 进度条
        progress = ttk.Progressbar(dialog, mode="indeterminate")
        progress.pack(fill=tk.X, padx=20, pady=3)

        # 结果列表
        ttk.Label(dialog, text="发现结果:").pack(pady=2)
        result_listbox = tk.Listbox(dialog, height=8)
        result_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=2)

        # 发现结果存储
        discovery_results = []

        def parse_ip_range(ip_str):
            """解析IP范围"""
            ips = []
            ip_str = ip_str.strip()

            # 处理CIDR格式 192.168.1.0/24
            if '/' in ip_str:
                try:
                    ip, mask = ip_str.split('/')
                    ip_parts = list(map(int, ip.split('.')))
                    mask = int(mask)

                    if mask == 24:
                        network = (ip_parts[0] << 24) + (ip_parts[1] << 16) + (ip_parts[2] << 8)
                        for i in range(1, 255):
                            ips.append(f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{i}")
                    elif mask == 16:
                        network = (ip_parts[0] << 24) + (ip_parts[1] << 16)
                        for i in range(1, 255):
                            for j in range(1, 255):
                                ips.append(f"{ip_parts[0]}.{ip_parts[1]}.{i}.{j}")
                except:
                    pass
            # 处理范围格式 192.168.1.1-254
            elif '-' in ip_str:
                try:
                    start_ip, end_ip = ip_str.split('-')
                    start_ip = start_ip.strip()
                    end_ip = end_ip.strip()

                    if '.' in end_ip:
                        # 完整IP范围 192.168.1.1-192.168.1.254
                        start_parts = list(map(int, start_ip.split('.')))
                        end_parts = list(map(int, end_ip.split('.')))

                        start_num = (start_parts[0] << 24) + (start_parts[1] << 16) + (start_parts[2] << 8) + start_parts[3]
                        end_num = (end_parts[0] << 24) + (end_parts[1] << 16) + (end_parts[2] << 8) + end_parts[3]

                        for num in range(start_num, end_num + 1):
                            ips.append(f"{(num >> 24) & 0xFF}.{(num >> 16) & 0xFF}.{(num >> 8) & 0xFF}.{num & 0xFF}")
                    else:
                        # 短格式 192.168.1.1-254
                        prefix = '.'.join(start_ip.split('.')[:-1])
                        for i in range(int(start_ip.split('.')[-1]), int(end_ip) + 1):
                            ips.append(f"{prefix}.{i}")
                except:
                    pass
            else:
                ips.append(ip_str)

            return ips

        def scan_port(ip, port, timeout=2):
            """扫描单个端口"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                return result == 0
            except:
                return False

        def scan_host(ip, ports, timeout=2):
            """扫描主机端口"""
            open_ports = []
            for port in ports:
                if scan_port(ip, port, timeout):
                    open_ports.append(port)
            return open_ports

        def get_banner(ip, port, timeout=3):
            """获取设备banner"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((ip, port))

                if port == 22:
                    sock.send(b"\n")
                    time.sleep(1)
                    banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()
                    return banner.strip()
                elif port == 23:
                    sock.send(b"\n")
                    time.sleep(1)
                    banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()
                    return banner.strip()[:100]
                elif port == 443:
                    sock.send(b"GET / HTTP/1.0\r\n\r\n")
                    time.sleep(1)
                    banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()
                    return banner.strip()[:100]
            except:
                pass
            return ""

        def identify_vendor_from_banner(banner):
            """从banner识别厂商"""
            banner_lower = banner.lower()

            if 'cisco' in banner_lower:
                return "Cisco"
            elif 'huawei' in banner_lower or 'huawei' in banner_lower:
                return "Huawei"
            elif 'h3c' in banner_lower or 'hp' in banner_lower:
                return "H3C"
            elif 'juniper' in banner_lower or 'junos' in banner_lower:
                return "Juniper"
            elif 'fortinet' in banner_lower or 'fortigate' in banner_lower:
                return "Fortinet"
            elif '锐捷' in banner or 'ruijie' in banner_lower:
                return "锐捷"
            elif '深信服' in banner or 'sangfor' in banner_lower:
                return "深信服"
            else:
                return "其他"

        def start_discovery():
            """开始发现"""
            nonlocal discovery_results

            ip_range = ip_entry.get().strip()
            if not ip_range:
                messagebox.showwarning("警告", "请输入IP范围")
                return

            # 获取要扫描的端口
            ports = [port for port, var in port_vars.items() if var.get()]
            if not ports:
                messagebox.showwarning("警告", "请选择至少一个端口")
                return

            progress.start()
            discovery_btn.config(state=tk.DISABLED)

            # 解析IP列表
            ips = parse_ip_range(ip_range)
            total = len(ips)
            discovered = []

            self.log(f"开始扫描 {total} 个IP...")

            # 并发扫描
            max_workers = threads_var.get()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ip = {executor.submit(scan_host, ip, ports): ip for ip in ips}

                completed = 0
                for future in as_completed(future_to_ip):
                    ip = future_to_ip[future]
                    completed += 1

                    try:
                        open_ports = future.result()
                        if open_ports:
                            # 尝试获取banner
                            vendor = "其他"
                            if identify_vendor.get():
                                for port in open_ports:
                                    banner = get_banner(ip, port)
                                    if banner:
                                        vendor = identify_vendor_from_banner(banner)
                                        break

                            # 确定设备类型和端口
                            device_type = "路由器"
                            if 22 in open_ports:
                                main_port = 22
                                protocol = "SSH"
                            elif 23 in open_ports:
                                main_port = 23
                                protocol = "Telnet"
                            else:
                                main_port = open_ports[0]
                                protocol = "SSH"

                            device_info = {
                                "id": f"dev_{int(time.time())}_{len(discovered)}",
                                "ip": ip,
                                "port": main_port,
                                "protocol": protocol,
                                "vendor": vendor,
                                "device_type": device_type,
                                "model": "",
                                "username": "",
                                "password": "",
                                "enable": "",
                                "status": "在线",
                                "last_inspect": "未巡检"
                            }
                            discovered.append(device_info)

                            # 更新UI - 只在发现新设备时更新
                            result_listbox.insert(tk.END, f"{ip}:{main_port} - {vendor} ({protocol})")
                            self.log(f"发现设备: {ip}:{main_port} - {vendor}")
                    except Exception as e:
                        pass

                    # 更新进度 - 只每10个IP更新一次UI，避免频繁刷新造成卡顿
                    if completed % 10 == 0 or completed == total:
                        progress['value'] = (completed / total) * 100
                        dialog.update()

            progress.stop()
            progress['value'] = 0
            discovery_btn.config(state=tk.NORMAL)

            discovery_results = discovered
            self.log(f"发现完成，共发现 {len(discovered)} 台设备")

            # 启用添加到设备库按钮
            add_btn.config(state=tk.NORMAL)

        def add_discovered_devices():
            """添加发现的设备到列表"""
            for device in discovery_results:
                self.devices.append(device)

            self.save_devices()
            self.refresh_device_list()
            self.log(f"已添加 {len(discovery_results)} 台设备到列表")
            messagebox.showinfo("成功", f"已添加 {len(discovery_results)} 台设备")
            dialog.destroy()

        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, pady=3)

        discovery_btn = ttk.Button(btn_frame, text="开始扫描", command=start_discovery)
        discovery_btn.pack(side=tk.LEFT, padx=5)

        add_btn = ttk.Button(btn_frame, text="添加到设备库", command=add_discovered_devices, state=tk.DISABLED)
        add_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_add_device_dialog(self):
        """显示添加设备对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加设备")
        dialog.geometry("480x520")
        dialog.transient(self.root)
        dialog.grab_set()

        # 表单
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # 设备类型
        ttk.Label(form_frame, text="设备类型:").grid(row=0, column=0, sticky=tk.W, pady=8)
        device_type = ttk.Combobox(form_frame, values=self.commands_data.get("device_types", []), state="readonly", width=25)
        device_type.grid(row=0, column=1, sticky=tk.W, pady=8)
        device_type.current(0)

        # 厂商
        ttk.Label(form_frame, text="厂商:").grid(row=1, column=0, sticky=tk.W, pady=8)
        vendor = ttk.Combobox(form_frame, values=self.commands_data.get("vendors", []), state="readonly", width=25)
        vendor.grid(row=1, column=1, sticky=tk.W, pady=8)
        vendor.current(0)

        # 型号
        ttk.Label(form_frame, text="型号:").grid(row=2, column=0, sticky=tk.W, pady=8)
        model = ttk.Entry(form_frame, width=28)
        model.grid(row=2, column=1, sticky=tk.W, pady=8)

        # IP
        ttk.Label(form_frame, text="IP地址:").grid(row=3, column=0, sticky=tk.W, pady=8)
        ip = ttk.Entry(form_frame, width=28)
        ip.grid(row=3, column=1, sticky=tk.W, pady=8)

        # 端口
        # 协议/端口（在同行）
        ttk.Label(form_frame, text="协议/端口:").grid(row=4, column=0, sticky=tk.W, pady=8)
        protocol_port_frame = ttk.Frame(form_frame)
        protocol_port_frame.grid(row=4, column=1, sticky=tk.W, pady=8)
        protocol = ttk.Combobox(protocol_port_frame, values=["SSH", "Telnet"], state="readonly", width=10)
        protocol.pack(side=tk.LEFT)
        protocol.current(0)
        ttk.Label(protocol_port_frame, text=" / ").pack(side=tk.LEFT)
        port = ttk.Entry(protocol_port_frame, width=10)
        port.insert(0, "22")
        port.pack(side=tk.LEFT)

        # 协议与端口联动
        def on_protocol_change(*args):
            if protocol.get() == "Telnet":
                port.delete(0, tk.END)
                port.insert(0, "23")
            else:
                port.delete(0, tk.END)
                port.insert(0, "22")
        protocol.bind("<<ComboboxSelected>>", on_protocol_change)

        # 用户名
        ttk.Label(form_frame, text="用户名:").grid(row=5, column=0, sticky=tk.W, pady=8)
        username = ttk.Entry(form_frame, width=28)
        username.grid(row=5, column=1, sticky=tk.W, pady=8)

        # 密码
        ttk.Label(form_frame, text="密码:").grid(row=6, column=0, sticky=tk.W, pady=8)
        password = ttk.Entry(form_frame, show="*", width=28)
        password.grid(row=6, column=1, sticky=tk.W, pady=8)

        # Enable密码
        ttk.Label(form_frame, text="特权密码:").grid(row=7, column=0, sticky=tk.W, pady=8)
        enable = ttk.Entry(form_frame, show="*", width=28)
        enable.grid(row=7, column=1, sticky=tk.W, pady=8)

        def save():
            """保存设备"""
            if not ip.get().strip():
                messagebox.showwarning("警告", "请输入IP地址")
                return

            device = {
                "id": f"dev_{int(time.time())}",
                "device_type": device_type.get(),
                "vendor": vendor.get(),
                "model": model.get(),
                "ip": ip.get().strip(),
                "port": port.get().strip(),
                "protocol": protocol.get(),
                "username": username.get(),
                "password": password.get(),
                "enable": enable.get(),
                "status": "未知",
                "last_inspect": "未巡检"
            }

            self.devices.append(device)
            self.save_devices()
            self.refresh_device_list()
            self.log(f"添加设备: {ip.get()}")
            messagebox.showinfo("成功", "设备添加成功")
            dialog.destroy()

        # 按钮
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="保存", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def on_device_double_click(self, event):
        """双击设备查看详情"""
        selection = self.device_tree.selection()
        if selection:
            item = self.device_tree.item(selection[0])
            values = item['values']
            index = values[0] - 1

            if 0 <= index < len(self.devices):
                self.current_device_id = self.devices[index]["id"]
                self.load_device_info(index)

    def load_device_info(self, index):
        """加载设备信息到表单"""
        device = self.devices[index]

        self.info_device_type.set(device.get("device_type", ""))
        self.info_vendor.set(device.get("vendor", ""))
        self.info_model.delete(0, tk.END)
        self.info_model.insert(0, device.get("model", ""))
        self.info_ip.delete(0, tk.END)
        self.info_ip.insert(0, device.get("ip", ""))
        self.info_port.delete(0, tk.END)
        self.info_port.insert(0, device.get("port", "22"))
        self.info_protocol.set(device.get("protocol", "SSH"))
        self.info_username.delete(0, tk.END)
        self.info_username.insert(0, device.get("username", ""))
        self.info_password.delete(0, tk.END)
        self.info_password.insert(0, device.get("password", ""))
        self.info_enable.delete(0, tk.END)
        self.info_enable.insert(0, device.get("enable", ""))

        self.selected_device_index = index
        self.log(f"选中设备: {device.get('ip', '')}")

    def save_device_info(self):
        """保存设备信息修改"""
        if self.selected_device_index is None:
            messagebox.showwarning("警告", "请先选择设备")
            return

        device = self.devices[self.selected_device_index]

        device["device_type"] = self.info_device_type.get()
        device["vendor"] = self.info_vendor.get()
        device["model"] = self.info_model.get()
        device["ip"] = self.info_ip.get()
        device["port"] = self.info_port.get()
        device["protocol"] = self.info_protocol.get()
        device["username"] = self.info_username.get()
        device["password"] = self.info_password.get()
        device["enable"] = self.info_enable.get()

        self.save_devices()
        self.refresh_device_list()
        self.log(f"保存设备信息: {device.get('ip', '')}")
        messagebox.showinfo("成功", "设备信息已保存")

    def delete_device(self):
        """删除设备"""
        if self.selected_device_index is None:
            messagebox.showwarning("警告", "请先选择设备")
            return

        if messagebox.askyesno("确认", "确定要删除该设备吗?"):
            device = self.devices.pop(self.selected_device_index)
            self.save_devices()
            self.refresh_device_list()
            self.selected_device_index = None
            self.log(f"删除设备: {device.get('ip', '')}")

    def test_connection(self):
        """测试设备连接"""
        if self.selected_device_index is None:
            messagebox.showwarning("警告", "请先选择设备")
            return

        device = self.devices[self.selected_device_index]

        self.log(f"测试连接: {device.get('ip', '')}...")

        # 简单TCP连接测试
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((device.get("ip"), int(device.get("port", 22))))
            sock.close()

            if result == 0:
                device["status"] = "在线"
                self.refresh_device_list()
                self.log(f"设备在线: {device.get('ip', '')}")
                messagebox.showinfo("成功", "设备连接正常")
            else:
                device["status"] = "离线"
                self.refresh_device_list()
                self.log(f"设备离线: {device.get('ip', '')}")
                messagebox.showwarning("失败", "无法连接到设备")
        except Exception as e:
            device["status"] = "离线"
            self.refresh_device_list()
            self.log(f"连接错误: {device.get('ip', '')} - {str(e)}")
            messagebox.showerror("错误", f"连接失败: {str(e)}")

    def show_device_context_menu(self, event):
        """显示设备右键菜单"""
        # 选择点击的行
        item = self.device_tree.identify_row(event.y)
        if item:
            self.device_tree.selection_set(item)
            self.device_tree.focus(item)

            menu = tk.Menu(self.device_tree, tearoff=0)
            menu.add_command(label="查看详情", command=lambda: self.on_device_double_click(None))
            menu.add_command(label="编辑", command=lambda: self.on_device_double_click(None))
            menu.add_command(label="执行巡检", command=self.run_inspection)
            menu.add_command(label="删除", command=self.delete_device)
            menu.post(event.x_root, event.y_root)

    def run_inspection(self):
        """执行巡检"""
        if not self.devices:
            messagebox.showwarning("警告", "没有设备")
            return

        # 选择要巡检的设备
        dialog = tk.Toplevel(self.root)
        dialog.title("选择巡检设备")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        ttk.Label(dialog, text="选择要执行巡检的设备:").pack(pady=3)

        # 设备列表
        listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=3)

        for device in self.devices:
            listbox.insert(tk.END, f"{device.get('ip', '')} - {device.get('vendor', '')} - {device.get('device_type', '')}")

        # 全选按钮
        def select_all():
            listbox.select_set(0, tk.END)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=3)
        ttk.Button(btn_frame, text="全选", command=select_all).pack(side=tk.LEFT, padx=5)

        def start_inspect():
            """开始巡检"""
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("警告", "请选择设备")
                return

            selected_devices = [self.devices[i] for i in selection]
            dialog.destroy()

            # 创建巡检线程
            thread = threading.Thread(target=self.execute_inspection, args=(selected_devices,))
            thread.daemon = True
            thread.start()

        ttk.Button(btn_frame, text="开始巡检", command=start_inspect).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def execute_inspection(self, devices):
        """执行巡检命令"""
        self.inspect_running = True
        self.result_text.delete(1.0, tk.END)

        results = []

        for device in devices:
            if not self.inspect_running:
                break

            ip = device.get("ip", "")
            self.log(f"开始巡检: {ip}")
            self.result_text.insert(tk.END, f"\n{'='*60}\n")
            self.result_text.insert(tk.END, f"设备: {ip} ({device.get('vendor', '')} {device.get('device_type', '')})\n")
            self.result_text.insert(tk.END, f"{'='*60}\n\n")

            device_result = {
                "ip": ip,
                "vendor": device.get("vendor", ""),
                "device_type": device.get("device_type", ""),
                "commands": [],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # 获取该设备的巡检命令
            commands = self.get_commands_for_device(device)

            for cmd_info in commands:
                cmd = cmd_info.get("command", "")
                desc = cmd_info.get("description", "")

                self.result_text.insert(tk.END, f"\n>>> {desc}\n")
                self.result_text.insert(tk.END, f"命令: {cmd}\n")
                self.result_text.insert(tk.END, "-" * 40 + "\n")

                # 执行命令
                output = self.execute_command(device, cmd)

                self.result_text.insert(tk.END, output + "\n")
                self.result_text.see(tk.END)

                device_result["commands"].append({
                    "description": desc,
                    "command": cmd,
                    "output": output
                })

            results.append(device_result)

            # 更新设备最后巡检时间
            device["last_inspect"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.save_devices()
        self.refresh_device_list()

        self.log("巡检完成")
        self.result_text.insert(tk.END, "\n\n" + "="*60 + "\n")
        self.result_text.insert(tk.END, "巡检完成！\n")

        # 保存结果
        self.save_inspection_results(results)

        self.inspect_running = False

    def get_commands_for_device(self, device):
        """获取设备的巡检命令"""
        vendor = device.get("vendor", "").lower()
        device_type = device.get("device_type", "").lower()

        commands = []
        for cmd in self.commands_data.get("commands", []):
            cmd_vendor = cmd.get("vendor", "").lower()
            cmd_type = cmd.get("device_type", "").lower()
            
            # 匹配厂商：精确匹配或包含匹配
            vendor_match = (cmd_vendor == vendor or 
                          cmd_vendor in vendor or 
                          vendor in cmd_vendor or
                          cmd_vendor == "其他")
            
            # 匹配设备类型：精确匹配或包含匹配
            type_match = (cmd_type == device_type or 
                         cmd_type in device_type or 
                         device_type in cmd_type or
                         cmd_type == "其他")
            
            if vendor_match and type_match:
                commands.append(cmd)

        return commands

    def execute_command(self, device, command):
        """执行命令"""
        try:
            # 尝试使用netmiko
            if NETMIKO_AVAILABLE:
                return self._execute_with_netmiko(device, command)
            else:
                return self._execute_with_paramiko(device, command)
        except Exception as e:
            return f"执行失败: {str(e)}"

    def _execute_with_netmiko(self, device, command):
        """使用netmiko执行命令"""
        try:
            port = int(device.get("port", 22))
            protocol = device.get("protocol", "SSH")  # 获取协议类型
            device_type = 'cisco_ios'  # 默认 SSH 类型
            
            # 根据厂商设置设备类型
            vendor = device.get("vendor", "").lower()
            if 'cisco' in vendor:
                device_type = 'cisco_ios'
            elif 'huawei' in vendor:
                device_type = 'huawei'
            elif 'h3c' in vendor:
                device_type = 'hp_comware'
            elif 'juniper' in vendor:
                device_type = 'juniper'
            elif 'fortinet' in vendor:
                device_type = 'fortinet'
            elif '锐捷' in vendor:
                device_type = 'ruijie_os'
            
            # Telnet 需要使用 _telnet 后缀（根据协议判断，不只是端口）
            if protocol == "Telnet":
                device_type = device_type + '_telnet'

            device_info = {
                'device_type': device_type,
                'host': device.get("ip"),
                'port': port,
                'username': device.get("username", ""),
                'password': device.get("password", ""),
                'secret': device.get("enable", ""),
                'timeout': 30,
                'global_delay_factor': 2,  # 增加全局延迟
            }

            conn = ConnectHandler(**device_info)

            # 根据厂商进入对应的特权/系统模式
            vendor_lower = vendor.lower()
            try:
                if 'huawei' in vendor_lower or 'h3c' in vendor_lower:
                    # 华为/H3C 进入系统视图
                    conn.send_command_timing("system-view", read_timeout=10)
                elif 'cisco' in vendor_lower or '锐捷' in vendor_lower or 'ruijie' in vendor_lower:
                    # Cisco/锐捷 进入特权模式（即使没有密码也要调用 enable，空密码会发送回车）
                    try:
                        conn.enable()
                    except:
                        pass  # 可能已经在特权模式，忽略错误
                elif 'juniper' in vendor_lower:
                    # Juniper 进入配置模式或 CLI
                    conn.send_command_timing("cli", read_timeout=10)
                elif 'fortinet' in vendor_lower:
                    # Fortinet 可能需要进入全局配置
                    pass  # Fortinet 通常在用户模式下也能执行很多命令
            except Exception as mode_e:
                # 进入特权模式失败，记录但继续尝试执行命令
                pass

            # 禁用分页，确保完整输出（不同厂商命令不同）
            try:
                if 'cisco' in vendor_lower or '锐捷' in vendor_lower or 'ruijie' in vendor_lower:
                    # Cisco IOS / 锐捷交换机
                    conn.send_command_timing("terminal length 0", read_timeout=10)
                    # 尝试防火墙命令（Cisco ASA 使用 terminal pager 0）
                    try:
                        conn.send_command_timing("terminal pager 0", read_timeout=5)
                    except:
                        pass
                elif 'huawei' in vendor_lower:
                    conn.send_command_timing("screen-length 0 temporary", read_timeout=10)
                elif 'h3c' in vendor_lower:
                    conn.send_command_timing("screen-length 0", read_timeout=10)
                elif 'juniper' in vendor_lower:
                    conn.send_command_timing("set cli screen-length 0", read_timeout=10)
            except:
                pass  # 忽略分页设置错误

            # 执行命令，处理分页问题
            output = self._send_command_with_pagination(conn, command)
            conn.disconnect()

            return output
        
        except Exception as e:
            return f"Netmiko执行失败: {str(e)}"

    def _send_command_with_pagination(self, conn, command):
        """发送命令并处理分页，自动按空格继续显示"""
        output = ""
        max_retries = 200  # 最多200次继续，防止死循环
        
        # 先发送命令获取初始输出
        conn.write_channel(command + "\n")
        time.sleep(1)  # 等待命令执行
        
        for i in range(max_retries):
            # 读取当前输出
            chunk = conn.read_channel()
            output += chunk
            
            # 检查是否有分页提示
            if "-- More --" in chunk or "--More--" in chunk or "---more---" in chunk.lower() or "more" in chunk.lower() and "--" in chunk:
                # 发送空格键继续，等待3秒让完整内容输出
                conn.write_channel(" ")
                time.sleep(3)
            else:
                # 没有分页了，等待一下确认没有更多内容
                time.sleep(1)
                # 再读一次确认
                extra = conn.read_channel()
                if extra.strip():
                    output += extra
                    # 如果还有内容再检查分页
                    if "-- More --" in extra or "--More--" in extra or "---more---" in extra.lower() or "more" in extra.lower() and "--" in extra:
                        continue
                
                # 如果输出不为空且没有更多内容，说明已经完成
                if output.strip():
                    break
                # 如果只有空输出，说明完成了
                if not chunk.strip() and not extra.strip():
                    break
        
        return output

    def _execute_with_paramiko(self, device, command):
        """使用paramiko执行命令"""
        try:
            import paramiko

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            client.connect(
                hostname=device.get("ip"),
                port=int(device.get("port", 22)),
                username=device.get("username", ""),
                password=device.get("password", ""),
                timeout=30
            )

            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode('utf-8', errors='ignore')
            client.close()

            return output
        except Exception as e:
            return f"Paramiko执行失败: {str(e)}\n\n提示: 请安装 netmiko 或 paramiko 库"

    def save_inspection_results(self, results):
        """保存巡检结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(self.base_dir, f"inspection_{timestamp}.json")

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        self.log(f"巡检结果已保存到: {result_file}")

    def export_report(self):
        """导出HTML报告"""
        if not self.devices:
            messagebox.showwarning("警告", "没有设备")
            return

        # 选择保存位置
        filename = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML文件", "*.html")],
            initialfile=f"巡检报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )

        if not filename:
            return

        # 生成HTML报告
        html = self.generate_html_report()

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        self.log(f"报告已导出: {filename}")
        messagebox.showinfo("成功", f"报告已导出到:\n{filename}")

    def generate_html_report(self):
        """生成HTML报告"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>网络设备巡检报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #1E3A5F; text-align: center; }
        .info { text-align: center; color: #666; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background: #1E3A5F; color: white; }
        tr:nth-child(even) { background: #f9f9f9; }
        .status-online { color: #4CAF50; font-weight: bold; }
        .status-offline { color: #F44336; font-weight: bold; }
        .device-section { margin: 30px 0; border: 1px solid #ddd; padding: 20px; }
        .device-title { font-size: 18px; color: #1E3A5F; margin-bottom: 15px; }
        .command-section { margin: 15px 0; padding: 10px; background: #f5f5f5; }
        .command-desc { font-weight: bold; color: #333; }
        .command-cmd { color: #666; font-family: monospace; }
        .command-output { background: #272822; color: #f8f8f2; padding: 10px; margin-top: 5px; white-space: pre-wrap; font-family: monospace; font-size: 12px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>网络设备巡检报告</h1>
        <div class="info">
            <p>生成时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            <p>设备总数: """ + str(len(self.devices)) + """</p>
        </div>

        <h2>设备清单</h2>
        <table>
            <tr>
                <th>序号</th>
                <th>IP</th>
                <th>设备类型</th>
                <th>厂商</th>
                <th>型号</th>
                <th>状态</th>
                <th>最后巡检</th>
            </tr>
"""

        for i, device in enumerate(self.devices, 1):
            status_class = "status-online" if device.get("status") == "在线" else "status-offline"
            html += f"""
            <tr>
                <td>{i}</td>
                <td>{device.get('ip', '')}</td>
                <td>{device.get('device_type', '')}</td>
                <td>{device.get('vendor', '')}</td>
                <td>{device.get('model', '')}</td>
                <td class="{status_class}">{device.get('status', '未知')}</td>
                <td>{device.get('last_inspect', '未巡检')}</td>
            </tr>
"""

        html += """
        </table>

        <h2>详细巡检结果</h2>
"""

        # 加载最新的巡检结果
        result_files = [f for f in os.listdir(self.base_dir) if f.startswith("inspection_") and f.endswith(".json")]
        if result_files:
            result_files.sort(reverse=True)
            latest_file = os.path.join(self.base_dir, result_files[0])

            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    inspection_results = json.load(f)

                for device_result in inspection_results:
                    html += f"""
        <div class="device-section">
            <div class="device-title">{device_result.get('ip', '')} - {device_result.get('vendor', '')} {device_result.get('device_type', '')}</div>
            <p>巡检时间: {device_result.get('timestamp', '')}</p>
"""
                    for cmd_result in device_result.get("commands", []):
                        html += f"""
            <div class="command-section">
                <div class="command-desc">{cmd_result.get('description', '')}</div>
                <div class="command-cmd">{cmd_result.get('command', '')}</div>
                <div class="command-output">{cmd_result.get('output', '')}</div>
            </div>
"""
                    html += """
        </div>
"""
            except:
                pass

        html += """
    </div>
</body>
</html>
"""
        return html

    def show_commands_manager(self):
        """显示命令管理对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("巡检命令管理")
        dialog.geometry("900x600")
        dialog.transient(self.root)

        # 顶部筛选
        filter_frame = ttk.Frame(dialog)
        filter_frame.pack(fill=tk.X, padx=10, pady=3)

        ttk.Label(filter_frame, text="厂商:").pack(side=tk.LEFT, padx=5)
        vendor_filter = ttk.Combobox(filter_frame, values=["全部"] + self.commands_data.get("vendors", []), state="readonly", width=15)
        vendor_filter.current(0)
        vendor_filter.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="设备类型:").pack(side=tk.LEFT, padx=5)
        type_filter = ttk.Combobox(filter_frame, values=["全部"] + self.commands_data.get("device_types", []), state="readonly", width=15)
        type_filter.current(0)
        type_filter.pack(side=tk.LEFT, padx=5)

        # 命令列表
        columns = ("厂商", "设备类型", "分类", "描述", "命令")
        cmd_tree = ttk.Treeview(dialog, columns=columns, show="headings", height=20)

        for col in columns:
            cmd_tree.heading(col, text=col)
            cmd_tree.column(col, width=150)

        cmd_tree.column("命令", width=250)

        # 滚动条
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=cmd_tree.yview)
        cmd_tree.configure(yscrollcommand=vsb.set)

        cmd_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=2)
        vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=5, padx=(0, 10))

        def load_commands():
            """加载命令"""
            for item in cmd_tree.get_children():
                cmd_tree.delete(item)

            vendor = vendor_filter.get()
            device_type = type_filter.get()

            for cmd in self.commands_data.get("commands", []):
                if vendor != "全部" and cmd.get("vendor") != vendor:
                    continue
                if device_type != "全部" and cmd.get("device_type") != device_type:
                    continue

                cmd_tree.insert("", tk.END, values=(
                    cmd.get("vendor", ""),
                    cmd.get("device_type", ""),
                    cmd.get("category", ""),
                    cmd.get("description", ""),
                    cmd.get("command", "")
                ))

        def add_command():
            """添加命令"""
            add_dialog = tk.Toplevel(dialog)
            add_dialog.title("添加巡检命令")
            add_dialog.geometry("500x400")
            add_dialog.transient(dialog)

            form_frame = ttk.Frame(add_dialog, padding=20)
            form_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(form_frame, text="厂商:").grid(row=0, column=0, sticky=tk.W, pady=2)
            cmd_vendor = ttk.Combobox(form_frame, values=self.commands_data.get("vendors", []), state="readonly", width=25)
            cmd_vendor.grid(row=0, column=1, sticky=tk.W, pady=2)
            cmd_vendor.current(0)

            ttk.Label(form_frame, text="设备类型:").grid(row=1, column=0, sticky=tk.W, pady=2)
            cmd_type = ttk.Combobox(form_frame, values=self.commands_data.get("device_types", []), state="readonly", width=25)
            cmd_type.grid(row=1, column=1, sticky=tk.W, pady=2)
            cmd_type.current(0)

            ttk.Label(form_frame, text="分类:").grid(row=2, column=0, sticky=tk.W, pady=2)
            cmd_category = ttk.Entry(form_frame, width=28)
            cmd_category.grid(row=2, column=1, sticky=tk.W, pady=2)

            ttk.Label(form_frame, text="描述:").grid(row=3, column=0, sticky=tk.W, pady=2)
            cmd_desc = ttk.Entry(form_frame, width=28)
            cmd_desc.grid(row=3, column=1, sticky=tk.W, pady=2)

            ttk.Label(form_frame, text="命令:").grid(row=4, column=0, sticky=tk.W, pady=2)
            cmd_cmd = tk.Text(form_frame, width=30, height=8)
            cmd_cmd.grid(row=4, column=1, sticky=tk.W, pady=2)

            def save():
                if not cmd_desc.get() or not cmd_cmd.get("1.0", tk.END).strip():
                    messagebox.showwarning("警告", "请填写完整信息")
                    return

                new_cmd = {
                    "vendor": cmd_vendor.get(),
                    "device_type": cmd_type.get(),
                    "category": cmd_category.get(),
                    "description": cmd_desc.get(),
                    "command": cmd_cmd.get("1.0", tk.END).strip()
                }

                self.commands_data["commands"].append(new_cmd)

                with open(self.commands_file, 'w', encoding='utf-8') as f:
                    json.dump(self.commands_data, f, ensure_ascii=False, indent=2)

                load_commands()
                messagebox.showinfo("成功", "命令添加成功")
                add_dialog.destroy()

            ttk.Button(form_frame, text="保存", command=save).grid(row=5, column=1, sticky=tk.W, pady=3)

        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, pady=3)

        ttk.Button(btn_frame, text="添加命令", command=add_command).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=load_commands).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # 绑定筛选事件
        vendor_filter.bind("<<ComboboxSelected>>", lambda e: load_commands())
        type_filter.bind("<<ComboboxSelected>>", lambda e: load_commands())

        # 初始加载
        load_commands()

    def show_about(self):
        """显示关于对话框"""
        about_dialog = tk.Toplevel(self.root)
        about_dialog.title("关于 IT工具箱")
        about_dialog.geometry("400x300")
        about_dialog.transient(self.root)
        about_dialog.resizable(False, False)

        # 主框架
        main_frame = ttk.Frame(about_dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = tk.Label(main_frame, text="IT工具箱", font=("Helvetica", 20, "bold"), fg="#1976D2")
        title_label.pack(pady=3)

        # 版本
        version_label = tk.Label(main_frame, text="版本: 1.0.0", font=("Helvetica", 12))
        version_label.pack(pady=2)

        # 描述
        desc_label = tk.Label(main_frame, text="网络设备巡检工具", font=("Helvetica", 11))
        desc_label.pack(pady=2)

        # 分隔线
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        # 功能说明
        features = [
            "• 支持路由器、交换机、防火墙等设备",
            "• 自动设备发现",
            "• 自定义巡检命令",
            "• 多厂商支持（Cisco、华为、H3C、锐捷等）",
            "• SSH/Telnet 双协议支持"
        ]
        for feat in features:
            tk.Label(main_frame, text=feat, font=("Helvetica", 10), anchor=tk.W).pack(fill=tk.X, pady=2)

        # 确定按钮
        ttk.Button(main_frame, text="确定", command=about_dialog.destroy).pack(pady=20)

    def show_subnet_scan_dialog(self):
        """显示子网扫描对话框 - 支持整个子网段扫描"""
        dialog = tk.Toplevel(self.root)
        dialog.title("子网扫描")
        dialog.geometry("580x560")
        dialog.transient(self.root)
        dialog.grab_set()

        # 说明
        ttk.Label(dialog, text="子网扫描 - 扫描整个网段的主机", font=("Helvetica", 12, "bold")).pack(pady=3)
        ttk.Label(dialog, text="支持格式: 192.168.1.0/24 或 192.168.1.0/16 或 10.0.0.0/8", font=("Arial", 9)).pack()

        # IP网段输入
        input_frame = ttk.Frame(dialog)
        input_frame.pack(pady=10, fill=tk.X, padx=10)
        
        ttk.Label(input_frame, text="目标网段:").pack(side=tk.LEFT, padx=5)
        subnet_entry = ttk.Entry(input_frame, width=30)
        subnet_entry.pack(side=tk.LEFT, padx=5)
        subnet_entry.insert(0, "192.168.1.0/24")

        # 扫描选项
        options_frame = ttk.LabelFrame(dialog, text="扫描选项", padding=10)
        options_frame.pack(pady=10, fill=tk.X, padx=10)

        # Ping扫描
        ping_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="执行Ping扫描 (检测主机存活)", variable=ping_var).pack(anchor=tk.W)

        # 端口扫描
        port_frame = ttk.Frame(options_frame)
        port_frame.pack(fill=tk.X, pady=2)
        
        port_scan_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(port_frame, text="扫描常用端口:", variable=port_scan_var).pack(side=tk.LEFT)
        
        port_entry = ttk.Entry(port_frame, width=40)
        port_entry.pack(side=tk.LEFT, padx=5)
        port_entry.insert(0, "22,23,80,443,3389,8080")

        # 超时设置
        timeout_frame = ttk.Frame(options_frame)
        timeout_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(timeout_frame, text="超时时间(秒):").pack(side=tk.LEFT)
        timeout_var = tk.IntVar(value=2)
        ttk.Spinbox(timeout_frame, from_=1, to=10, textvariable=timeout_var, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(timeout_frame, text="并发数:").pack(side=tk.LEFT, padx=(20,0))
        threads_var = tk.IntVar(value=100)
        ttk.Spinbox(timeout_frame, from_=10, to=500, textvariable=threads_var, width=8).pack(side=tk.LEFT, padx=5)

        # 进度显示
        progress_frame = ttk.Frame(dialog)
        progress_frame.pack(fill=tk.X, padx=20, pady=2)
        
        progress_label = ttk.Label(progress_frame, text="准备扫描...")
        progress_label.pack(side=tk.LEFT)
        
        progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
        progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 结果区域
        result_frame = ttk.LabelFrame(dialog, text="扫描结果", padding=5)
        result_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=10)

        # 创建Treeview显示结果
        columns = ("IP", "状态", "响应时间", "开放端口")
        result_tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=5)
        
        for col in columns:
            result_tree.heading(col, text=col)
        
        result_tree.column("IP", width=120, anchor="center")
        result_tree.column("状态", width=80, anchor="center")
        result_tree.column("响应时间", width=100, anchor="center")
        result_tree.column("开放端口", width=200, anchor="w")

        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=result_tree.yview)
        result_tree.configure(yscrollcommand=vsb.set)
        
        result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 统计标签
        stats_label = ttk.Label(dialog, text="存活主机: 0 | 总主机: 0")
        stats_label.pack(pady=2)

        scan_results = []
        scan_running = False

        def parse_subnet(subnet_str):
            """解析子网，返回所有IP列表"""
            try:
                import ipaddress
                network = ipaddress.ip_network(subnet_str, strict=False)
                # 返回所有主机地址（排除网络地址和广播地址）
                return [str(ip) for ip in network.hosts()]
            except:
                messagebox.showerror("错误", "无效的网段格式，请使用 CIDR 格式如 192.168.1.0/24")
                return []

        def ping_host(ip, timeout):
            """Ping单个主机"""
            import platform
            import subprocess
            
            system = platform.system().lower()
            
            if system == "windows":
                cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
            else:  # Linux/Mac
                cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
            
            try:
                start_time = time.time()
                result = subprocess.run(cmd, capture_output=True, timeout=timeout + 2)
                elapsed = time.time() - start_time
                
                if result.returncode == 0:
                    return True, f"{elapsed*1000:.1f}ms"
                return False, None
            except:
                return False, None

        def scan_ports(ip, ports, timeout):
            """扫描指定端口"""
            open_ports = []
            for port in ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    if result == 0:
                        open_ports.append(port)
                except:
                    pass
            return open_ports

        def start_scan():
            """开始扫描"""
            nonlocal scan_running, scan_results
            
            subnet = subnet_entry.get().strip()
            if not subnet:
                messagebox.showwarning("警告", "请输入目标网段")
                return
            
            # 解析网段
            ips = parse_subnet(subnet)
            if not ips:
                return
            
            total = len(ips)
            if total > 65534:
                if not messagebox.askyesno("确认", f"网段包含 {total} 个IP，扫描可能需要较长时间，是否继续?"):
                    return
            
            scan_running = True
            scan_results = []
            
            # 清空结果
            for item in result_tree.get_children():
                result_tree.delete(item)
            
            # 解析端口
            ports = []
            if port_scan_var.get():
                try:
                    ports = [int(p.strip()) for p in port_entry.get().split(",") if p.strip()]
                except:
                    ports = [22, 23, 80, 443]
            
            timeout = timeout_var.get()
            max_workers = threads_var.get()
            
            self.log(f"开始子网扫描: {subnet} ({total} 个IP)")
            progress_label.config(text=f"正在扫描 {subnet}...")
            
            alive_count = 0
            completed = 0
            
            def scan_single(ip):
                """扫描单个IP"""
                is_alive = False
                response_time = None
                open_ports = []
                
                # Ping扫描
                if ping_var.get():
                    is_alive, response_time = ping_host(ip, timeout)
                
                # 端口扫描（无论Ping是否成功都扫描，或者只在Ping成功时扫描）
                if port_scan_var.get() and ports:
                    open_ports = scan_ports(ip, ports, timeout)
                    if open_ports and not is_alive:
                        is_alive = True  # 有开放端口也认为存活
                
                return ip, is_alive, response_time, open_ports
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ip = {executor.submit(scan_single, ip): ip for ip in ips}
                
                for future in as_completed(future_to_ip):
                    if not scan_running:
                        break
                    
                    ip, is_alive, response_time, open_ports = future.result()
                    completed += 1
                    
                    if is_alive:
                        alive_count += 1
                        status = "在线"
                        rt = response_time if response_time else "N/A"
                        ports_str = ", ".join(map(str, open_ports)) if open_ports else "无"
                        
                        result_tree.insert("", tk.END, values=(ip, status, rt, ports_str))
                        scan_results.append({
                            "ip": ip,
                            "status": "online",
                            "response_time": rt,
                            "open_ports": open_ports
                        })
                        self.log(f"发现主机: {ip} (端口: {ports_str})")
                    
                    # 更新进度
                    if completed % 10 == 0 or completed == total:
                        progress_bar['value'] = (completed / total) * 100
                        stats_label.config(text=f"存活主机: {alive_count} | 总主机: {total} | 已完成: {completed}/{total}")
                        dialog.update_idletasks()
            
            scan_running = False
            progress_label.config(text="扫描完成")
            progress_bar['value'] = 0
            self.log(f"子网扫描完成: {subnet}，发现 {alive_count} 台存活主机")
            messagebox.showinfo("完成", f"扫描完成!\n网段: {subnet}\n存活主机: {alive_count}/{total}")

        def stop_scan():
            """停止扫描"""
            nonlocal scan_running
            scan_running = False
            progress_label.config(text="扫描已停止")

        def export_results():
            """导出扫描结果"""
            if not scan_results:
                messagebox.showwarning("警告", "没有扫描结果可导出")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")],
                initialfile=f"子网扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            if not filename:
                return
            
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(scan_results, f, ensure_ascii=False, indent=2)
                else:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("IP,状态,响应时间,开放端口\n")
                        for r in scan_results:
                            ports = ";".join(map(str, r.get('open_ports', [])))
                            f.write(f"{r['ip']},{r['status']},{r.get('response_time', 'N/A')},{ports}\n")
                
                self.log(f"扫描结果已导出: {filename}")
                messagebox.showinfo("成功", f"结果已导出到:\n{filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")

        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, pady=3)
        
        ttk.Button(btn_frame, text="开始扫描", command=start_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="停止", command=stop_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="导出结果", command=export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_batch_ping_dialog(self):
        """显示批量Ping对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("批量Ping")
        dialog.geometry("580x560")
        dialog.transient(self.root)
        dialog.grab_set()

        # 说明
        ttk.Label(dialog, text="批量Ping - 快速检测多台主机连通性", font=("Helvetica", 12, "bold")).pack(pady=3)

        # 输入方式选择
        input_frame = ttk.LabelFrame(dialog, text="目标主机", padding=10)
        input_frame.pack(pady=10, fill=tk.X, padx=10)

        # 单选按钮
        input_mode = tk.StringVar(value="list")
        
        # 列表输入
        ttk.Radiobutton(input_frame, text="IP列表 (每行一个)", variable=input_mode, value="list").pack(anchor=tk.W)
        
        ip_text = scrolledtext.ScrolledText(input_frame, width=50, height=3)
        ip_text.pack(fill=tk.X, pady=2)
        ip_text.insert(tk.END, "192.168.1.1\n192.168.1.254\n8.8.8.8")

        # 网段输入
        subnet_frame = ttk.Frame(input_frame)
        subnet_frame.pack(fill=tk.X, pady=2)
        
        ttk.Radiobutton(subnet_frame, text="扫描网段:", variable=input_mode, value="subnet").pack(side=tk.LEFT)
        subnet_entry = ttk.Entry(subnet_frame, width=25)
        subnet_entry.pack(side=tk.LEFT, padx=5)
        subnet_entry.insert(0, "192.168.1.0/24")

        # 选项
        options_frame = ttk.LabelFrame(dialog, text="Ping选项", padding=10)
        options_frame.pack(pady=10, fill=tk.X, padx=10)

        opt_frame = ttk.Frame(options_frame)
        opt_frame.pack(fill=tk.X)
        
        ttk.Label(opt_frame, text="Ping次数:").pack(side=tk.LEFT)
        count_var = tk.IntVar(value=1)
        ttk.Spinbox(opt_frame, from_=1, to=10, textvariable=count_var, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(opt_frame, text="超时(秒):").pack(side=tk.LEFT, padx=(20,0))
        timeout_var = tk.IntVar(value=2)
        ttk.Spinbox(opt_frame, from_=1, to=10, textvariable=timeout_var, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(opt_frame, text="并发数:").pack(side=tk.LEFT, padx=(20,0))
        threads_var = tk.IntVar(value=50)
        ttk.Spinbox(opt_frame, from_=10, to=200, textvariable=threads_var, width=8).pack(side=tk.LEFT, padx=5)

        # 进度
        progress_frame = ttk.Frame(dialog)
        progress_frame.pack(fill=tk.X, padx=20, pady=2)
        
        progress_label = ttk.Label(progress_frame, text="准备开始...")
        progress_label.pack(side=tk.LEFT)
        
        progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
        progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 结果区域
        result_frame = ttk.LabelFrame(dialog, text="Ping结果", padding=5)
        result_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=10)

        # 创建Treeview
        columns = ("IP", "状态", "丢包率", "平均延迟", "详情")
        result_tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=5)
        
        for col in columns:
            result_tree.heading(col, text=col)
        
        result_tree.column("IP", width=120, anchor="center")
        result_tree.column("状态", width=80, anchor="center")
        result_tree.column("丢包率", width=80, anchor="center")
        result_tree.column("平均延迟", width=100, anchor="center")
        result_tree.column("详情", width=150, anchor="w")

        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=result_tree.yview)
        result_tree.configure(yscrollcommand=vsb.set)
        
        result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 统计
        stats_label = ttk.Label(dialog, text="成功: 0 | 失败: 0 | 总计: 0")
        stats_label.pack(pady=2)

        ping_running = False
        ping_results = []

        def parse_ips():
            """解析IP列表"""
            if input_mode.get() == "list":
                text = ip_text.get("1.0", tk.END).strip()
                ips = [ip.strip() for ip in text.split('\n') if ip.strip()]
                return ips
            else:
                # 解析网段
                try:
                    import ipaddress
                    network = ipaddress.ip_network(subnet_entry.get().strip(), strict=False)
                    return [str(ip) for ip in network.hosts()]
                except Exception as e:
                    messagebox.showerror("错误", f"无效的网段格式: {str(e)}")
                    return []

        def ping_host_detailed(ip, count, timeout):
            """执行详细Ping"""
            import platform
            import subprocess
            import re
            
            system = platform.system().lower()
            
            if system == "windows":
                cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), ip]
            else:
                cmd = ["ping", "-c", str(count), "-W", str(timeout), ip]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout * count + 5)
                output = result.stdout
                
                if result.returncode != 0:
                    return False, "100%", "N/A", "无法连通"
                
                # 解析输出
                if system == "windows":
                    # Windows格式: 已发送 = 4，已接收 = 4，丢失 = 0 (0% 丢失)
                    loss_match = re.search(r'(\d+)% 丢失|lost = (\d+)', output)
                    loss = loss_match.group(1) + "%" if loss_match and loss_match.group(1) else "0%"
                    
                    # 平均延迟
                    avg_match = re.search(r'平均 = (\d+)ms|Average = (\d+)ms', output)
                    avg = avg_match.group(1) + "ms" if avg_match and avg_match.group(1) else \
                          avg_match.group(2) + "ms" if avg_match else "<1ms"
                else:
                    # Linux/Mac格式: 4 packets transmitted, 4 received, 0% packet loss
                    loss_match = re.search(r'(\d+)% packet loss', output)
                    loss = loss_match.group(1) + "%" if loss_match else "0%"
                    
                    # 平均延迟
                    avg_match = re.search(r'min/avg/max.*?= .*?/(\d+\.?\d*)/', output)
                    avg = avg_match.group(1) + "ms" if avg_match else "<1ms"
                
                return True, loss, avg, "正常"
            except subprocess.TimeoutExpired:
                return False, "100%", "N/A", "超时"
            except Exception as e:
                return False, "100%", "N/A", str(e)

        def start_ping():
            """开始批量Ping"""
            nonlocal ping_running, ping_results
            
            ips = parse_ips()
            if not ips:
                messagebox.showwarning("警告", "请输入有效的IP地址")
                return
            
            total = len(ips)
            if total > 1000:
                if not messagebox.askyesno("确认", f"将要Ping {total} 个IP，是否继续?"):
                    return
            
            ping_running = True
            ping_results = []
            
            # 清空结果
            for item in result_tree.get_children():
                result_tree.delete(item)
            
            count = count_var.get()
            timeout = timeout_var.get()
            max_workers = threads_var.get()
            
            self.log(f"开始批量Ping {total} 个主机...")
            progress_label.config(text=f"正在Ping {total} 个主机...")
            
            success_count = 0
            fail_count = 0
            completed = 0
            
            def ping_single(ip):
                success, loss, avg, detail = ping_host_detailed(ip, count, timeout)
                return ip, success, loss, avg, detail
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ip = {executor.submit(ping_single, ip): ip for ip in ips}
                
                for future in as_completed(future_to_ip):
                    if not ping_running:
                        break
                    
                    ip, success, loss, avg, detail = future.result()
                    completed += 1
                    
                    if success:
                        success_count += 1
                        status = "成功"
                        tag = "success"
                    else:
                        fail_count += 1
                        status = "失败"
                        tag = "fail"
                    
                    result_tree.insert("", tk.END, values=(ip, status, loss, avg, detail), tags=(tag,))
                    ping_results.append({
                        "ip": ip,
                        "status": "success" if success else "fail",
                        "loss": loss,
                        "avg_latency": avg,
                        "detail": detail
                    })
                    
                    # 更新进度
                    if completed % 5 == 0 or completed == total:
                        progress_bar['value'] = (completed / total) * 100
                        stats_label.config(text=f"成功: {success_count} | 失败: {fail_count} | 总计: {total} | 已完成: {completed}")
                        dialog.update_idletasks()
            
            ping_running = False
            progress_label.config(text="Ping完成")
            progress_bar['value'] = 0
            self.log(f"批量Ping完成: 成功 {success_count}/{total}")
            
            # 设置标签颜色
            result_tree.tag_configure("success", foreground="#4CAF50")
            result_tree.tag_configure("fail", foreground="#F44336")

        def stop_ping():
            """停止Ping"""
            nonlocal ping_running
            ping_running = False
            progress_label.config(text="已停止")

        def export_ping_results():
            """导出Ping结果"""
            if not ping_results:
                messagebox.showwarning("警告", "没有结果可导出")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")],
                initialfile=f"Ping结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            if not filename:
                return
            
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(ping_results, f, ensure_ascii=False, indent=2)
                else:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("IP,状态,丢包率,平均延迟,详情\n")
                        for r in ping_results:
                            f.write(f"{r['ip']},{r['status']},{r['loss']},{r['avg_latency']},{r['detail']}\n")
                
                self.log(f"Ping结果已导出: {filename}")
                messagebox.showinfo("成功", f"结果已导出到:\n{filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")

        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, pady=3)
        
        ttk.Button(btn_frame, text="开始Ping", command=start_ping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="停止", command=stop_ping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="导出结果", command=export_ping_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)


def main():
    """主函数"""
    # 检查依赖
    if not NETMIKO_AVAILABLE and not PARAMIKO_AVAILABLE:
        print("警告: 未安装 netmiko 或 paramiko 库，巡检功能将受限")
        print("请运行: pip install netmiko")

    # 创建窗口
    root = tk.Tk()

    # 设置样式 - 浅蓝色主题
    style = ttk.Style()
    style.theme_use('clam')

    # 浅蓝色配色方案
    style.configure("TFrame", background="#E3F2FD")
    style.configure("TLabel", background="#E3F2FD", foreground="#1565C0")
    style.configure("TButton", background="#1976D2", foreground="white", padding=5)
    style.map("TButton", background=[("active", "#1565C0")])
    style.configure("TEntry", fieldbackground="white", foreground="#1565C0")
    style.configure("TCombobox", fieldbackground="white", foreground="#1565C0")
    style.configure("TLabelframe", background="#E3F2FD", foreground="#1565C0")
    style.configure("TLabelframe.Label", background="#E3F2FD", foreground="#1565C0", font=("Helvetica", 10, "bold"))
    style.configure("Treeview", background="white", foreground="#1565C0", fieldbackground="white")
    style.configure("Treeview.Heading", background="#BBDEFB", foreground="#1565C0", font=("Helvetica", 10, "bold"))
    style.configure("TNotebook", background="#E3F2FD", tabmargins=[2, 5, 2, 0])
    style.configure("TNotebook.Tab", background="#BBDEFB", foreground="#1565C0", padding=[10, 5])
    style.map("TNotebook.Tab", background=[("selected", "#1976D2")], foreground=[("selected", "white")])

    # 启动应用
    app = DeviceInspectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
