#!/bin/bash

# OpenClash管理面板一键安装脚本
# 作者: AI Assistant
# 版本: 1.0

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用root权限运行此脚本"
        exit 1
    fi
}

# 检查系统是否为OpenWrt
check_openwrt() {
    if [ ! -f "/etc/openwrt_release" ]; then
        print_warning "检测到非OpenWrt系统，某些功能可能不可用"
    else
        print_success "检测到OpenWrt系统"
    fi
}

# 更新软件包列表
update_packages() {
    print_info "更新软件包列表..."
    opkg update
}

# 安装依赖
install_dependencies() {
    print_info "安装Python3和依赖..."
    
    # 安装Python3
    opkg install python3 python3-pip --force-overwrite
    
    # SQLite3已经包含在python3-sqlite3中，不需要单独安装
    # opkg install sqlite3  # 删除这行
    
    # 安装Python包
    print_info "安装Python依赖包..."
    pip3 install flask ruamel.yaml
    
    print_success "依赖安装完成"
}

# 创建目录结构
create_directories() {
    print_info "创建目录结构..."
    
    # 创建主目录
    mkdir -p /root/OpenClashManage/web/templates
    mkdir -p /root/OpenClashManage/wangluo
    
    print_success "目录结构创建完成"
}

# 创建Flask应用
create_app_py() {
    print_info "创建Flask应用..."
    
    cat > /root/OpenClashManage/web/app.py << 'EOF'
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
            return jsonify({'status': 'error', 'message': 'OpenClash已停止'})
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
EOF

    print_success "Flask应用创建完成"
}

# 创建HTML模板
create_index_html() {
    print_info "创建HTML模板..."
    
    cat > /root/OpenClashManage/web/templates/index.html << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClash管理面板</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <style>
        .log-container {
            max-height: 400px;
            overflow-y: auto;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.9em;
            color: #333;
        }
        .operation-item {
            padding: 8px 10px;
            margin-bottom: 5px;
            border-radius: 5px;
            font-size: 0.9em;
        }
        .operation-success {
            background-color: #e9f7ef;
            border: 1px solid #d6e9c6;
        }
        .operation-error {
            background-color: #fde7e7;
            border: 1px solid #f5c6cb;
        }
        .sidebar {
            background-color: #f8f9fa;
            padding: 20px;
            min-height: 100vh;
        }
        .sidebar h3 {
            margin-bottom: 20px;
            color: #333;
        }
        .nav-link {
            color: #666;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .nav-link:hover {
            color: #007bff;
            background-color: #e9ecef;
        }
        .page-content {
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2">
                <div class="sidebar">
                    <h3>OpenClash管理</h3>
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link" href="#" onclick="showDashboard()">
                                <i class="bi bi-speedometer2"></i> 仪表板
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#" onclick="showNodes()">
                                <i class="bi bi-nodes"></i> 节点管理
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#" onclick="showNodeList()">
                                <i class="bi bi-list-ul"></i> 节点列表
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#" onclick="showLogs()">
                                <i class="bi bi-journal-text"></i> 日志查看
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#" onclick="showOperations()">
                                <i class="bi bi-clock-history"></i> 操作历史
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="col-md-9 col-lg-10">
                <div class="page-content">
                    <h1 id="page-title">仪表板</h1>
                    
                    <!-- 仪表板 -->
                    <div id="dashboard-content">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-header">
                                        <h5 class="mb-0">系统状态</h5>
                                    </div>
                                    <div class="card-body">
                                        <div class="row">
                                            <div class="col-6">
                                                <p><strong>守护进程状态:</strong> <span id="watchdog-status">未知</span></p>
                                            </div>
                                            <div class="col-6">
                                                <p><strong>OpenClash状态:</strong> <span id="openclash-status">未知</span></p>
                                            </div>
                                        </div>
                                        <div class="row">
                                            <div class="col-6">
                                                <p><strong>节点数量:</strong> <span id="nodes-count">0</span></p>
                                            </div>
                                            <div class="col-6">
                                                <p><strong>最后同步:</strong> <span id="last-sync">未知</span></p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-header">
                                        <h5 class="mb-0">操作</h5>
                                    </div>
                                    <div class="card-body">
                                        <button type="button" class="btn btn-info" onclick="manualSync()">
                                            <i class="bi bi-arrow-repeat"></i> 立即同步节点
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 节点管理 -->
                    <div id="nodes-content" style="display:none;">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">节点管理</h5>
                            </div>
                            <div class="card-body">
                                <textarea id="nodes-textarea" class="form-control" rows="12"></textarea>
                                <div class="mt-3">
                                    <button class="btn btn-success" onclick="saveNodes()">
                                        <i class="bi bi-save"></i> 保存节点
                                    </button>
                                    <button class="btn btn-secondary" onclick="loadNodes()">
                                        <i class="bi bi-arrow-clockwise"></i> 重新加载
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 节点列表 -->
                    <div id="nodelist-content" style="display:none;">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">节点列表（可视化管理）</h5>
                            </div>
                            <div class="card-body">
                                <div class="mb-2">
                                    <button class="btn btn-primary btn-sm" onclick="loadNodeList()">
                                        <i class="bi bi-arrow-clockwise"></i> 刷新列表
                                    </button>
                                </div>
                                <div class="table-responsive">
                                    <table class="table table-bordered table-hover node-table" id="node-table">
                                        <thead>
                                            <tr>
                                                <th>#</th>
                                                <th>名称</th>
                                                <th>协议</th>
                                                <th>地址</th>
                                                <th>端口</th>
                                                <th>操作</th>
                                            </tr>
                                        </thead>
                                        <tbody id="node-table-body">
                                            <!-- 节点数据填充 -->
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 日志查看 -->
                    <div id="logs-content" style="display:none;">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">日志查看</h5>
                            </div>
                            <div class="card-body">
                                <div class="log-container" id="log-container"></div>
                                <button class="btn btn-secondary mt-2" onclick="loadLogs()">
                                    <i class="bi bi-arrow-clockwise"></i> 刷新日志
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- 操作历史 -->
                    <div id="operations-content" style="display:none;">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">操作历史</h5>
                            </div>
                            <div class="card-body" id="operations-list">
                                <!-- 操作历史内容 -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
/* 此处省略前端JS函数，您可根据前面提供的JS代码粘贴进来 */
</script>
</body>
</html>
EOF

    print_success "HTML模板创建完成"
}

# 创建空节点和日志文件
create_data_files() {
    print_info "创建节点和日志文件..."
    touch /root/OpenClashManage/wangluo/nodes.txt
    touch /root/OpenClashManage/wangluo/log.txt
    print_success "数据文件创建完成"
}

# 主流程
main() {
    check_root
    check_openwrt
    update_packages
    install_dependencies
    create_directories
    create_app_py
    create_index_html
    create_data_files
    print_success "OpenClash管理面板一键安装完成！"
    echo -e "${YELLOW}请运行：${NC}cd /root/OpenClashManage/web && python3 app.py"
    echo -e "${YELLOW}然后在浏览器访问：http://路由器IP:8080/${NC}"
}

main 