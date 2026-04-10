#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络设备巡检工具 - NetInspector
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
        self.root.title("网络设备巡检工具 - NetInspector v1.0")
        self.root.geometry("1200x800")
        
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
        if 'NetInspector.app' in self.base_dir:
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
        """初始化UI"""
        # 顶部工具栏
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="🔍 发现设备", command=self.show_discovery_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="➕ 添加设备", command=self.show_add_device_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="▶️ 执行巡检", command=self.run_inspection).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📊 导出报告", command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📝 命令管理", command=self.show_commands_manager).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="🔄 刷新", command=self.refresh_device_list).pack(side=tk.LEFT, padx=5)
        
        # 主内容区 - 左右分栏
        main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧设备列表
        left_frame = ttk.LabelFrame(main_frame, text="设备列表", padding=5)
        main_frame.add(left_frame, weight=2)
        
        # 设备表格
        columns = ("序号", "类型", "厂商", "型号", "IP", "端口", "状态", "最后巡检")
        self.device_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=15)
        
        # 设置列
        self.device_tree.heading("序号", text="序号")
        self.device_tree.heading("类型", text="设备类型")
        self.device_tree.heading("厂商", text="厂商")
        self.device_tree.heading("型号", text="型号")
        self.device_tree.heading("IP", text="IP地址")
        self.device_tree.heading("端口", text="端口")
        self.device_tree.heading("状态", text="状态")
        self.device_tree.heading("最后巡检", text="最后巡检时间")
        
        self.device_tree.column("序号", width=50, anchor="center")
        self.device_tree.column("类型", width=80, anchor="center")
        self.device_tree.column("厂商", width=80, anchor="center")
        self.device_tree.column("型号", width=100, anchor="center")
        self.device_tree.column("IP", width=120, anchor="center")
        self.device_tree.column("端口", width=60, anchor="center")
        self.device_tree.column("状态", width=70, anchor="center")
        self.device_tree.column("最后巡检", width=140, anchor="center")
        
        # 滚动条
        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=vsb.set)
        
        self.device_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定双击事件
        self.device_tree.bind("<Double-1>", self.on_device_double_click)
        
        # 右键菜单
        self.device_tree.bind("<Button-3>", self.show_device_context_menu)
        
        # 右侧详情面板
        right_frame = ttk.LabelFrame(main_frame, text="设备详情 / 巡检结果", padding=5)
        main_frame.add(right_frame, weight=3)
        
        # 详情Notebook
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 设备信息Tab
        info_frame = ttk.Frame(self.notebook)
        self.notebook.add(info_frame, text="设备信息")
        
        # 设备表单
        form_frame = ttk.Frame(info_frame, padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设备类型
        ttk.Label(form_frame, text="设备类型:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.info_device_type = ttk.Combobox(form_frame, values=self.commands_data.get("device_types", []), state="readonly", width=25)
        self.info_device_type.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # 厂商
        ttk.Label(form_frame, text="厂商:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.info_vendor = ttk.Combobox(form_frame, values=self.commands_data.get("vendors", []), state="readonly", width=25)
        self.info_vendor.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 型号
        ttk.Label(form_frame, text="型号:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.info_model = ttk.Entry(form_frame, width=28)
        self.info_model.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # IP
        ttk.Label(form_frame, text="IP地址:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.info_ip = ttk.Entry(form_frame, width=28)
        self.info_ip.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # 端口
        ttk.Label(form_frame, text="端口:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.info_port = ttk.Entry(form_frame, width=28)
        self.info_port.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # 协议
        ttk.Label(form_frame, text="协议:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.info_protocol = ttk.Combobox(form_frame, values=["SSH", "Telnet"], state="readonly", width=25)
        self.info_protocol.grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # 用户名
        ttk.Label(form_frame, text="用户名:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.info_username = ttk.Entry(form_frame, width=28)
        self.info_username.grid(row=6, column=1, sticky=tk.W, pady=5)
        
        # 密码
        ttk.Label(form_frame, text="密码:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.info_password = ttk.Entry(form_frame, show="*", width=28)
        self.info_password.grid(row=7, column=1, sticky=tk.W, pady=5)
        
        # Enable密码
        ttk.Label(form_frame, text="特权密码:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.info_enable = ttk.Entry(form_frame, show="*", width=28)
        self.info_enable.grid(row=8, column=1, sticky=tk.W, pady=5)
        
        # 按钮
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="保存修改", command=self.save_device_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除设备", command=self.delete_device).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="测试连接", command=self.test_connection).pack(side=tk.LEFT, padx=5)
        
        # 巡检结果Tab
        result_frame = ttk.Frame(self.notebook)
        self.notebook.add(result_frame, text="巡检结果")
        
        # 巡检输出文本框
        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, width=60, height=20)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 底部日志区域
        log_frame = ttk.LabelFrame(self.root, text="日志输出", padding=5)
        log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 当前选中的设备索引
        self.selected_device_index = None
        
        # 存储当前选择的设备ID
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
                device.get("port", "22"),
                status,
                last_inspect
            ), tags=(device.get("id", ""),))
    
    def show_discovery_dialog(self):
        """显示设备发现对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("设备发现")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # IP范围输入
        ttk.Label(dialog, text="IP范围或网段:").pack(pady=5)
        ip_entry = ttk.Entry(dialog, width=40)
        ip_entry.pack(pady=5)
        ttk.Label(dialog, text="例如: 192.168.1.1-254 或 192.168.1.0/24", font=("Arial", 9)).pack()
        
        # 端口选择
        ttk.Label(dialog, text="扫描端口:").pack(pady=5)
        ports_frame = ttk.Frame(dialog)
        ports_frame.pack(pady=5)
        
        port_vars = {}
        for port, name in [(22, "SSH"), (23, "Telnet"), (443, "HTTPS")]:
            var = tk.BooleanVar(value=True)
            port_vars[port] = var
            ttk.Checkbutton(ports_frame, text=f"{port} ({name})", variable=var).pack(side=tk.LEFT, padx=10)
        
        # 厂商识别
        ttk.Label(dialog, text="选项:").pack(pady=5)
        identify_vendor = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="自动识别厂商", variable=identify_vendor).pack()
        
        # 并发数
        ttk.Label(dialog, text="并发数:").pack(pady=5)
        threads_var = tk.IntVar(value=50)
        ttk.Spinbox(dialog, from_=10, to=200, textvariable=threads_var, width=10).pack()
        
        # 进度条
        progress = ttk.Progressbar(dialog, mode="indeterminate")
        progress.pack(fill=tk.X, padx=20, pady=10)
        
        # 结果列表
        ttk.Label(dialog, text="发现结果:").pack(pady=5)
        result_listbox = tk.Listbox(dialog, height=8)
        result_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
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
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        
        discovery_btn = ttk.Button(btn_frame, text="开始扫描", command=start_discovery)
        discovery_btn.pack(side=tk.LEFT, padx=5)
        
        add_btn = ttk.Button(btn_frame, text="添加到设备库", command=add_discovered_devices, state=tk.DISABLED)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def show_add_device_dialog(self):
        """显示添加设备对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加设备")
        dialog.geometry("450x400")
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
        ttk.Label(form_frame, text="端口:").grid(row=4, column=0, sticky=tk.W, pady=8)
        port = ttk.Entry(form_frame, width=28)
        port.insert(0, "22")
        port.grid(row=4, column=1, sticky=tk.W, pady=8)
        
        # 协议
        ttk.Label(form_frame, text="协议:").grid(row=5, column=0, sticky=tk.W, pady=8)
        protocol = ttk.Combobox(form_frame, values=["SSH", "Telnet"], state="readonly", width=25)
        protocol.current(0)
        protocol.grid(row=5, column=1, sticky=tk.W, pady=8)
        
        # 用户名
        ttk.Label(form_frame, text="用户名:").grid(row=6, column=0, sticky=tk.W, pady=8)
        username = ttk.Entry(form_frame, width=28)
        username.grid(row=6, column=1, sticky=tk.W, pady=8)
        
        # 密码
        ttk.Label(form_frame, text="密码:").grid(row=7, column=0, sticky=tk.W, pady=8)
        password = ttk.Entry(form_frame, show="*", width=28)
        password.grid(row=7, column=1, sticky=tk.W, pady=8)
        
        # Enable密码
        ttk.Label(form_frame, text="特权密码:").grid(row=8, column=0, sticky=tk.W, pady=8)
        enable = ttk.Entry(form_frame, show="*", width=28)
        enable.grid(row=8, column=1, sticky=tk.W, pady=8)
        
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
        
        ttk.Label(dialog, text="选择要执行巡检的设备:").pack(pady=10)
        
        # 设备列表
        listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for device in self.devices:
            listbox.insert(tk.END, f"{device.get('ip', '')} - {device.get('vendor', '')} - {device.get('device_type', '')}")
        
        # 全选按钮
        def select_all():
            listbox.select_set(0, tk.END)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
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
        vendor = device.get("vendor", "")
        device_type = device.get("device_type", "")
        
        commands = []
        for cmd in self.commands_data.get("commands", []):
            if cmd.get("vendor") == vendor or cmd.get("vendor") == "其他":
                if cmd.get("device_type") == device_type or cmd.get("device_type") == "其他":
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
            device_info = {
                'device_type': 'cisco_ios',  # 默认
                'host': device.get("ip"),
                'port': int(device.get("port", 22)),
                'username': device.get("username", ""),
                'password': device.get("password", ""),
                'secret': device.get("enable", ""),
                'timeout': 30,
            }
            
            # 根据厂商设置设备类型
            vendor = device.get("vendor", "").lower()
            if 'cisco' in vendor:
                device_info['device_type'] = 'cisco_ios'
            elif 'huawei' in vendor:
                device_info['device_type'] = 'huawei'
            elif 'h3c' in vendor:
                device_info['device_type'] = 'hp_comware'
            elif 'juniper' in vendor:
                device_info['device_type'] = 'juniper'
            elif 'fortinet' in vendor:
                device_info['device_type'] = 'fortinet'
            elif '锐捷' in vendor:
                device_info['device_type'] = 'ruijie_os'
            
            conn = ConnectHandler(**device_info)
            
            # 如果有enable密码，尝试进入特权模式
            if device.get("enable"):
                conn.enable()
            
            output = conn.send_command(command)
            conn.disconnect()
            
            return output
        except Exception as e:
            return f"Netmiko执行失败: {str(e)}"
    
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
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
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
        
        cmd_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
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
            
            ttk.Label(form_frame, text="厂商:").grid(row=0, column=0, sticky=tk.W, pady=5)
            cmd_vendor = ttk.Combobox(form_frame, values=self.commands_data.get("vendors", []), state="readonly", width=25)
            cmd_vendor.grid(row=0, column=1, sticky=tk.W, pady=5)
            cmd_vendor.current(0)
            
            ttk.Label(form_frame, text="设备类型:").grid(row=1, column=0, sticky=tk.W, pady=5)
            cmd_type = ttk.Combobox(form_frame, values=self.commands_data.get("device_types", []), state="readonly", width=25)
            cmd_type.grid(row=1, column=1, sticky=tk.W, pady=5)
            cmd_type.current(0)
            
            ttk.Label(form_frame, text="分类:").grid(row=2, column=0, sticky=tk.W, pady=5)
            cmd_category = ttk.Entry(form_frame, width=28)
            cmd_category.grid(row=2, column=1, sticky=tk.W, pady=5)
            
            ttk.Label(form_frame, text="描述:").grid(row=3, column=0, sticky=tk.W, pady=5)
            cmd_desc = ttk.Entry(form_frame, width=28)
            cmd_desc.grid(row=3, column=1, sticky=tk.W, pady=5)
            
            ttk.Label(form_frame, text="命令:").grid(row=4, column=0, sticky=tk.W, pady=5)
            cmd_cmd = tk.Text(form_frame, width=30, height=8)
            cmd_cmd.grid(row=4, column=1, sticky=tk.W, pady=5)
            
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
            
            ttk.Button(form_frame, text="保存", command=save).grid(row=5, column=1, sticky=tk.W, pady=10)
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        
        ttk.Button(btn_frame, text="添加命令", command=add_command).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=load_commands).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # 绑定筛选事件
        vendor_filter.bind("<<ComboboxSelected>>", lambda e: load_commands())
        type_filter.bind("<<ComboboxSelected>>", lambda e: load_commands())
        
        # 初始加载
        load_commands()


def main():
    """主函数"""
    # 检查依赖
    if not NETMIKO_AVAILABLE and not PARAMIKO_AVAILABLE:
        print("警告: 未安装 netmiko 或 paramiko 库，巡检功能将受限")
        print("请运行: pip install netmiko")
    
    # 创建窗口
    root = tk.Tk()
    
    # 设置样式
    style = ttk.Style()
    style.theme_use('clam')
    
    # 启动应用
    app = DeviceInspectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
