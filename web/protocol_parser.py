#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import re
import urllib.parse
from typing import Dict, Optional, List

class ProtocolParser:
    """多协议节点解析器"""
    
    def __init__(self):
        self.supported_protocols = {
            'ss': 'Shadowsocks',
            'vmess': 'VMess', 
            'vless': 'VLESS',
            'trojan': 'Trojan',
            'ssr': 'ShadowsocksR',
            'socks5': 'SOCKS5',
            'http': 'HTTP',
            'snell': 'Snell',
            'hysteria': 'Hysteria',
            'tuic': 'TUIC',
            'wireguard': 'WireGuard',
            'reality': 'Reality',
            'naive': 'NaiveProxy'
        }
    
    def parse_link(self, link: str) -> Optional[Dict]:
        """解析节点链接"""
        link = link.strip()
        
        # 移除可能的注释
        if '#' in link:
            link = link.split('#')[0]
        
        try:
            if link.startswith('ss://'):
                return self._parse_shadowsocks(link)
            elif link.startswith('vmess://'):
                return self._parse_vmess(link)
            elif link.startswith('vless://'):
                return self._parse_vless(link)
            elif link.startswith('trojan://'):
                return self._parse_trojan(link)
            elif link.startswith('ssr://'):
                return self._parse_shadowsocksr(link)
            elif link.startswith('hysteria://'):
                return self._parse_hysteria(link)
            elif link.startswith('tuic://'):
                return self._parse_tuic(link)
            elif link.startswith('snell://'):
                return self._parse_snell(link)
            elif link.startswith('socks5://'):
                return self._parse_socks5(link)
            elif link.startswith('http://'):
                return self._parse_http(link)
            else:
                return None
        except Exception as e:
            return {'error': f'解析失败: {str(e)}', 'raw': link}
    
    def _parse_shadowsocks(self, link: str) -> Dict:
        """解析Shadowsocks链接"""
        # ss://base64(method:password@host:port)
        try:
            # 移除 ss:// 前缀
            encoded = link[5:]
            
            # 处理可能的 @ 符号
            if '@' in encoded:
                # 新格式: ss://base64(method:password@host:port)
                decoded = base64.b64decode(encoded).decode('utf-8')
                method_password, host_port = decoded.split('@')
                method, password = method_password.split(':')
                host, port = host_port.split(':')
            else:
                # 旧格式: ss://host:port:method:password
                parts = encoded.split(':')
                if len(parts) >= 4:
                    host = parts[0]
                    port = parts[1]
                    method = parts[2]
                    password = parts[3]
                else:
                    return {'error': 'Shadowsocks格式错误'}
            
            return {
                'type': 'ss',
                'name': f'SS-{host}:{port}',
                'server': host,
                'port': int(port),
                'method': method,
                'password': password
            }
        except Exception as e:
            return {'error': f'Shadowsocks解析失败: {str(e)}'}
    
    def _parse_vmess(self, link: str) -> Dict:
        """解析VMess链接"""
        try:
            # vmess://base64(json)
            encoded = link[8:]
            decoded = base64.b64decode(encoded).decode('utf-8')
            config = json.loads(decoded)
            
            return {
                'type': 'vmess',
                'name': config.get('ps', f'VMess-{config.get("add")}:{config.get("port")}'),
                'server': config.get('add'),
                'port': int(config.get('port')),
                'uuid': config.get('id'),
                'alterId': config.get('aid', 0),
                'security': config.get('scy', 'auto'),
                'network': config.get('net', 'tcp'),
                'wsPath': config.get('path', ''),
                'wsHost': config.get('host', ''),
                'tls': config.get('tls', 'none'),
                'sni': config.get('sni', '')
            }
        except Exception as e:
            return {'error': f'VMess解析失败: {str(e)}'}
    
    def _parse_vless(self, link: str) -> Dict:
        """解析VLESS链接"""
        try:
            # vless://uuid@host:port?type=ws&security=tls#name
            parsed = urllib.parse.urlparse(link)
            uuid = parsed.username
            host = parsed.hostname
            port = parsed.port
            name = parsed.fragment or f'VLESS-{host}:{port}'
            
            # 解析查询参数
            query = urllib.parse.parse_qs(parsed.query)
            
            return {
                'type': 'vless',
                'name': name,
                'server': host,
                'port': port,
                'uuid': uuid,
                'network': query.get('type', ['tcp'])[0],
                'security': query.get('security', ['none'])[0],
                'path': query.get('path', [''])[0],
                'host': query.get('host', [''])[0],
                'sni': query.get('sni', [''])[0]
            }
        except Exception as e:
            return {'error': f'VLESS解析失败: {str(e)}'}
    
    def _parse_trojan(self, link: str) -> Dict:
        """解析Trojan链接"""
        try:
            # trojan://password@host:port#name
            parsed = urllib.parse.urlparse(link)
            password = parsed.username
            host = parsed.hostname
            port = parsed.port
            name = parsed.fragment or f'Trojan-{host}:{port}'
            
            # 解析查询参数
            query = urllib.parse.parse_qs(parsed.query)
            
            return {
                'type': 'trojan',
                'name': name,
                'server': host,
                'port': port,
                'password': password,
                'sni': query.get('sni', [''])[0],
                'network': query.get('type', ['tcp'])[0]
            }
        except Exception as e:
            return {'error': f'Trojan解析失败: {str(e)}'}
    
    def _parse_shadowsocksr(self, link: str) -> Dict:
        """解析ShadowsocksR链接"""
        try:
            # ssr://base64(host:port:protocol:method:obfs:password_base64/?obfsparam=xxx&protoparam=xxx&remarks=xxx&group=xxx)
            encoded = link[6:]
            decoded = base64.b64decode(encoded).decode('utf-8')
            
            # 分离配置和参数
            if '?' in decoded:
                config_part, params_part = decoded.split('?', 1)
                params = urllib.parse.parse_qs(params_part)
            else:
                config_part = decoded
                params = {}
            
            # 解析配置部分
            parts = config_part.split(':')
            if len(parts) >= 6:
                host = parts[0]
                port = parts[1]
                protocol = parts[2]
                method = parts[3]
                obfs = parts[4]
                password = base64.b64decode(parts[5]).decode('utf-8')
                
                name = base64.b64decode(params.get('remarks', [''])[0]).decode('utf-8') if params.get('remarks') else f'SSR-{host}:{port}'
                
                return {
                    'type': 'ssr',
                    'name': name,
                    'server': host,
                    'port': int(port),
                    'protocol': protocol,
                    'method': method,
                    'obfs': obfs,
                    'password': password,
                    'obfsparam': base64.b64decode(params.get('obfsparam', [''])[0]).decode('utf-8') if params.get('obfsparam') else '',
                    'protoparam': base64.b64decode(params.get('protoparam', [''])[0]).decode('utf-8') if params.get('protoparam') else ''
                }
            else:
                return {'error': 'ShadowsocksR格式错误'}
        except Exception as e:
            return {'error': f'ShadowsocksR解析失败: {str(e)}'}
    
    def _parse_hysteria(self, link: str) -> Dict:
        """解析Hysteria链接"""
        try:
            # hysteria://host:port?protocol=udp&auth=xxx&peer=xxx&insecure=1&upmbps=100&downmbps=100&alpn=h3#name
            parsed = urllib.parse.urlparse(link)
            host = parsed.hostname
            port = parsed.port
            name = parsed.fragment or f'Hysteria-{host}:{port}'
            
            query = urllib.parse.parse_qs(parsed.query)
            
            return {
                'type': 'hysteria',
                'name': name,
                'server': host,
                'port': port,
                'protocol': query.get('protocol', ['udp'])[0],
                'auth': query.get('auth', [''])[0],
                'peer': query.get('peer', [''])[0],
                'insecure': query.get('insecure', ['0'])[0] == '1',
                'upmbps': int(query.get('upmbps', ['100'])[0]),
                'downmbps': int(query.get('downmbps', ['100'])[0]),
                'alpn': query.get('alpn', ['h3'])[0]
            }
        except Exception as e:
            return {'error': f'Hysteria解析失败: {str(e)}'}
    
    def _parse_tuic(self, link: str) -> Dict:
        """解析TUIC链接"""
        try:
            # tuic://uuid:password@host:port?congestion_control=bbr&udp_relay_mode=native&alpn=h3&allow_insecure=1#name
            parsed = urllib.parse.urlparse(link)
            uuid_password = parsed.username.split(':')
            uuid = uuid_password[0]
            password = uuid_password[1] if len(uuid_password) > 1 else ''
            host = parsed.hostname
            port = parsed.port
            name = parsed.fragment or f'TUIC-{host}:{port}'
            
            query = urllib.parse.parse_qs(parsed.query)
            
            return {
                'type': 'tuic',
                'name': name,
                'server': host,
                'port': port,
                'uuid': uuid,
                'password': password,
                'congestion_control': query.get('congestion_control', ['bbr'])[0],
                'udp_relay_mode': query.get('udp_relay_mode', ['native'])[0],
                'alpn': query.get('alpn', ['h3'])[0],
                'allow_insecure': query.get('allow_insecure', ['0'])[0] == '1'
            }
        except Exception as e:
            return {'error': f'TUIC解析失败: {str(e)}'}
    
    def _parse_socks5(self, link: str) -> Dict:
        """解析SOCKS5链接"""
        try:
            # socks5://username:password@host:port#name
            parsed = urllib.parse.urlparse(link)
            username = parsed.username
            password = parsed.password
            host = parsed.hostname
            port = parsed.port
            name = parsed.fragment or f'SOCKS5-{host}:{port}'
            
            return {
                'type': 'socks5',
                'name': name,
                'server': host,
                'port': port,
                'username': username,
                'password': password
            }
        except Exception as e:
            return {'error': f'SOCKS5解析失败: {str(e)}'}
    
    def _parse_http(self, link: str) -> Dict:
        """解析HTTP代理链接"""
        try:
            # http://username:password@host:port#name
            parsed = urllib.parse.urlparse(link)
            username = parsed.username
            password = parsed.password
            host = parsed.hostname
            port = parsed.port
            name = parsed.fragment or f'HTTP-{host}:{port}'
            
            return {
                'type': 'http',
                'name': name,
                'server': host,
                'port': port,
                'username': username,
                'password': password
            }
        except Exception as e:
            return {'error': f'HTTP解析失败: {str(e)}'}
    
    def _parse_snell(self, link: str) -> Dict:
        """解析Snell链接"""
        try:
            # snell://password@host:port?obfs=http&obfs-host=xxx#name
            parsed = urllib.parse.urlparse(link)
            password = parsed.username
            host = parsed.hostname
            port = parsed.port
            name = parsed.fragment or f'Snell-{host}:{port}'
            
            query = urllib.parse.parse_qs(parsed.query)
            
            return {
                'type': 'snell',
                'name': name,
                'server': host,
                'port': port,
                'password': password,
                'obfs': query.get('obfs', ['none'])[0],
                'obfs-host': query.get('obfs-host', [''])[0]
            }
        except Exception as e:
            return {'error': f'Snell解析失败: {str(e)}'}
    
    def generate_link(self, node: Dict) -> str:
        """根据节点配置生成链接"""
        node_type = node.get('type', '')
        
        if node_type == 'ss':
            return self._generate_shadowsocks_link(node)
        elif node_type == 'vmess':
            return self._generate_vmess_link(node)
        elif node_type == 'vless':
            return self._generate_vless_link(node)
        elif node_type == 'trojan':
            return self._generate_trojan_link(node)
        # 更多协议的生成方法...
        
        return ''
    
    def _generate_shadowsocks_link(self, node: Dict) -> str:
        """生成Shadowsocks链接"""
        try:
            method = node.get('method', 'aes-256-gcm')
            password = node.get('password', '')
            server = node.get('server', '')
            port = node.get('port', 443)
            
            # 新格式: ss://base64(method:password@host:port)
            content = f"{method}:{password}@{server}:{port}"
            encoded = base64.b64encode(content.encode()).decode()
            return f"ss://{encoded}#{node.get('name', '')}"
        except Exception:
            return ''
    
    def _generate_vmess_link(self, node: Dict) -> str:
        """生成VMess链接"""
        try:
            config = {
                'v': '2',
                'ps': node.get('name', ''),
                'add': node.get('server', ''),
                'port': node.get('port', 443),
                'id': node.get('uuid', ''),
                'aid': node.get('alterId', 0),
                'scy': node.get('security', 'auto'),
                'net': node.get('network', 'tcp'),
                'type': 'none',
                'host': node.get('wsHost', ''),
                'path': node.get('wsPath', ''),
                'tls': node.get('tls', 'none'),
                'sni': node.get('sni', '')
            }
            
            encoded = base64.b64encode(json.dumps(config).encode()).decode()
            return f"vmess://{encoded}"
        except Exception:
            return ''
    
    def _generate_vless_link(self, node: Dict) -> str:
        """生成VLESS链接"""
        try:
            uuid = node.get('uuid', '')
            server = node.get('server', '')
            port = node.get('port', 443)
            name = node.get('name', '')
            
            # 构建查询参数
            params = []
            if node.get('network') and node.get('network') != 'tcp':
                params.append(f"type={node.get('network')}")
            if node.get('security') and node.get('security') != 'none':
                params.append(f"security={node.get('security')}")
            if node.get('path'):
                params.append(f"path={node.get('path')}")
            if node.get('host'):
                params.append(f"host={node.get('host')}")
            if node.get('sni'):
                params.append(f"sni={node.get('sni')}")
            
            query = '&'.join(params) if params else ''
            url = f"vless://{uuid}@{server}:{port}"
            if query:
                url += f"?{query}"
            if name:
                url += f"#{name}"
            
            return url
        except Exception:
            return ''
    
    def _generate_trojan_link(self, node: Dict) -> str:
        """生成Trojan链接"""
        try:
            password = node.get('password', '')
            server = node.get('server', '')
            port = node.get('port', 443)
            name = node.get('name', '')
            
            # 构建查询参数
            params = []
            if node.get('sni'):
                params.append(f"sni={node.get('sni')}")
            if node.get('network') and node.get('network') != 'tcp':
                params.append(f"type={node.get('network')}")
            
            query = '&'.join(params) if params else ''
            url = f"trojan://{password}@{server}:{port}"
            if query:
                url += f"?{query}"
            if name:
                url += f"#{name}"
            
            return url
        except Exception:
            return '' 