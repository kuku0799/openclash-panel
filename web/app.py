#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, jsonify, send_file
import os
import subprocess
import json
import sqlite3
from datetime import datetime
import threading
import time

from protocol_parser import ProtocolParser

app = Flask(__name__)

# 配置
ROOT_DIR = "/root/OpenClashManage"
NODES_FILE = f"{ROOT_DIR}/wangluo/nodes.txt"
LOG_FILE = f"{ROOT_DIR}/wangluo/log.txt"
CONFIG_FILE = "/etc/openclash/config.yaml"
PID_FILE = "/tmp/openclash_watchdog.pid"

# 数据库初始化
def init_db():
    conn = sqlite3.connect(f"{ROOT_DIR}/web/database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# 初始化数据库
init_db()

# 初始化协议解析器
parser = ProtocolParser()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """获取系统状态"""
    status = {
        'watchdog_running': os.path.exists(PID_FILE),
        'openclash_running': check_openclash_status(),
        'nodes_count': get_nodes_count(),
        'config_exists': os.path.exists(CONFIG_FILE),
        'last_sync': get_last_sync_time()
    }
    return jsonify(status)

@app.route('/api/logs')
def get_logs():
    """获取日志"""
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = f.readlines()
        return jsonify({'logs': logs[-100:]})  # 返回最后100行
    except:
        return jsonify({'logs': []})

@app.route('/api/nodes')
def get_nodes():
    """获取节点文件内容"""
    try:
        with open(NODES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except:
        return jsonify({'content': ''})

@app.route('/api/nodes', methods=['POST'])
def update_nodes():
    """更新节点文件"""
    try:
        content = request.json.get('content', '')
        with open(NODES_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 记录操作
        record_operation('update_nodes', 'success', '节点文件已更新')
        
        return jsonify({'status': 'success', 'message': '节点文件已更新'})
    except Exception as e:
        record_operation('update_nodes', 'error', str(e))
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    """手动触发同步"""
    try:
        # 执行同步脚本
        result = subprocess.run(['python3', f'{ROOT_DIR}/zr.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            record_operation('manual_sync', 'success', '手动同步成功')
            return jsonify({'status': 'success', 'message': '同步成功'})
        else:
            record_operation('manual_sync', 'error', result.stderr)
            return jsonify({'status': 'error', 'message': result.stderr})
    except Exception as e:
        record_operation('manual_sync', 'error', str(e))
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/watchdog', methods=['POST'])
def toggle_watchdog():
    """启动/停止守护进程"""
    action = request.json.get('action')
    
    if action == 'start':
        try:
            subprocess.Popen(['bash', f'{ROOT_DIR}/jk.sh'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            record_operation('start_watchdog', 'success', '守护进程已启动')
            return jsonify({'status': 'success', 'message': '守护进程已启动'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    
    elif action == 'stop':
        try:
            if os.path.exists(PID_FILE):
                with open(PID_FILE, 'r') as f:
                    pid = f.read().strip()
                subprocess.run(['kill', pid])
                os.remove(PID_FILE)
            record_operation('stop_watchdog', 'success', '守护进程已停止')
            return jsonify({'status': 'success', 'message': '守护进程已停止'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/openclash', methods=['POST'])
def control_openclash():
    """控制OpenClash服务"""
    action = request.json.get('action')
    
    try:
        if action == 'restart':
            subprocess.run(['/etc/init.d/openclash', 'restart'])
            record_operation('restart_openclash', 'success', 'OpenClash已重启')
            return jsonify({'status': 'success', 'message': 'OpenClash已重启'})
        elif action == 'stop':
            subprocess.run(['/etc/init.d/openclash', 'stop'])
            record_operation('stop_openclash', 'success', 'OpenClash已停止')
            return jsonify({'status': 'success', 'message': 'OpenClash已停止'})
        elif action == 'start':
            subprocess.run(['/etc/init.d/openclash', 'start'])
            record_operation('start_openclash', 'success', 'OpenClash已启动')
            return jsonify({'status': 'success', 'message': 'OpenClash已启动'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# 辅助函数
def check_openclash_status():
    """检查OpenClash状态"""
    try:
        result = subprocess.run(['/etc/init.d/openclash', 'status'], 
                              capture_output=True, text=True)
        return 'running' in result.stdout.lower()
    except:
        return False

def get_nodes_count():
    """获取节点数量"""
    try:
        with open(NODES_FILE, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        return len(lines)
    except:
        return 0

def get_last_sync_time():
    """获取最后同步时间"""
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines):
                if '同步完成' in line or '配置写入完成' in line:
                    return line.split(' ')[0] + ' ' + line.split(' ')[1]
    except:
        pass
    return '未知'

def record_operation(operation, status, message):
    """记录操作到数据库"""
    conn = sqlite3.connect(f"{ROOT_DIR}/web/database.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO operations (operation, status, message)
        VALUES (?, ?, ?)
    ''', (operation, status, message))
    conn.commit()
    conn.close()

@app.route('/api/operations')
def get_operations():
    """获取操作历史"""
    conn = sqlite3.connect(f"{ROOT_DIR}/web/database.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT operation, status, message, timestamp 
        FROM operations 
        ORDER BY timestamp DESC 
        LIMIT 50
    ''')
    operations = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'operations': [
            {
                'operation': op[0],
                'status': op[1],
                'message': op[2],
                'timestamp': op[3]
            }
            for op in operations
        ]
    })

@app.route('/api/parse_nodes')
def parse_nodes_api():
    """解析节点文件并返回节点列表"""
    try:
        nodes = []
        with open('/root/OpenClashManage/wangluo/nodes.txt', 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            
            for idx, line in enumerate(lines):
                # 解析节点信息
                node_info = {
                    "name": f"节点{idx+1}",
                    "type": "Shadowsocks",
                    "server": line,
                    "port": "",
                }
                
                # 尝试从链接中提取更多信息
                if line.startswith('ss://'):
                    try:
                        # 解析Shadowsocks链接
                        import base64
                        import urllib.parse
                        
                        # 移除 ss:// 前缀
                        encoded = line[5:]
                        
                        # 分离配置和备注
                        if '#' in encoded:
                            config_part, name_part = encoded.split('#', 1)
                            node_info["name"] = urllib.parse.unquote(name_part)
                        else:
                            config_part = encoded
                        
                        # 解析base64部分
                        if '@' in config_part:
                            method_password, host_port = config_part.split('@')
                            method, password = method_password.split(':')
                            host, port = host_port.split(':')
                            
                            node_info.update({
                                "name": node_info["name"],
                                "type": "Shadowsocks",
                                "server": host,
                                "port": port,
                                "method": method,
                                "password": password
                            })
                    except:
                        # 如果解析失败，保持原始信息
                        pass
                elif line.startswith('vmess://'):
                    node_info["type"] = "VMess"
                elif line.startswith('vless://'):
                    node_info["type"] = "VLESS"
                elif line.startswith('trojan://'):
                    node_info["type"] = "Trojan"
                elif line.startswith('ssr://'):
                    node_info["type"] = "ShadowsocksR"
                
                nodes.append(node_info)
        
        return jsonify({"nodes": nodes, "total": len(nodes)})
    except Exception as e:
        return jsonify({"nodes": [], "error": str(e)})

@app.route('/api/node/<int:node_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_node(node_id):
    """管理单个节点"""
    try:
        # 获取所有节点
        with open(NODES_FILE, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        if request.method == 'GET':
            # 获取节点信息
            if 0 <= node_id < len(lines):
                line = lines[node_id]
                result = parser.parse_link(line)
                return jsonify(result)
            else:
                return jsonify({'error': '节点不存在'}), 404
        
        elif request.method == 'PUT':
            # 更新节点
            data = request.json
            if 0 <= node_id < len(lines):
                # 生成新的链接
                new_link = parser.generate_link(data)
                if new_link:
                    lines[node_id] = new_link
                    with open(NODES_FILE, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    return jsonify({'status': 'success', 'message': '节点已更新'})
                else:
                    return jsonify({'error': '无法生成节点链接'}), 400
            else:
                return jsonify({'error': '节点不存在'}), 404
        
        elif request.method == 'DELETE':
            # 删除节点
            if 0 <= node_id < len(lines):
                lines.pop(node_id)
                with open(NODES_FILE, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                return jsonify({'status': 'success', 'message': '节点已删除'})
            else:
                return jsonify({'error': '节点不存在'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/protocols')
def get_protocols():
    """获取支持的协议列表"""
    return jsonify(parser.supported_protocols)

@app.route('/api/proxy_groups')
def get_proxy_groups():
    """获取策略组列表"""
    try:
        config_path = "/etc/openclash/config.yaml"
        if not os.path.exists(config_path):
            return jsonify({"groups": [], "error": "配置文件不存在"})
        
        with open(config_path, 'r', encoding='utf-8') as f:
            import yaml
            config = yaml.safe_load(f)
        
        groups = config.get('proxy-groups', [])
        return jsonify({"groups": groups})
    except Exception as e:
        return jsonify({"groups": [], "error": str(e)})

@app.route('/api/proxy_groups/<group_name>', methods=['GET', 'PUT'])
def manage_proxy_group(group_name):
    """管理单个策略组"""
    try:
        config_path = "/etc/openclash/config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            import yaml
            config = yaml.safe_load(f)
        
        groups = config.get('proxy-groups', [])
        group = None
        
        for g in groups:
            if g.get('name') == group_name:
                group = g
                break
        
        if request.method == 'GET':
            return jsonify(group or {})
        elif request.method == 'PUT':
            data = request.json
            if group:
                group.update(data)
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, default_flow_style=False)
                return jsonify({"status": "success", "message": "策略组已更新"})
            else:
                return jsonify({"status": "error", "message": "策略组不存在"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False) 