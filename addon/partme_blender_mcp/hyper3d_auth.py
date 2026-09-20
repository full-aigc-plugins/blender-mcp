"""Hyper3D MCP 客户端 OAuth 编排；OAuth Token 始终由 Codex/Claude Code 管理。"""
from __future__ import annotations

import shutil
import subprocess
import json
import re
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse


HYPER3D_MCP_NAME = 'hyper3d'
HYPER3D_MCP_URL = 'https://api.hyper3d.com/api/mcp'
SUPPORTED_CLIENTS = frozenset({'CODEX', 'CLAUDE'})
_AUTHORIZATION_URL = re.compile(r'https://[^\s]+')


def find_client(client: str) -> str | None:
    """查找客户端 CLI，不修改 PATH，也不启动下载或安装。"""
    client = _client(client)
    command = 'codex' if client == 'CODEX' else 'claude'
    found = shutil.which(command)
    if found:
        return found
    for root in (Path.home() / '.local/bin', Path('/opt/homebrew/bin'), Path('/usr/local/bin')):
        candidate = root / command
        if candidate.is_file() and candidate.stat().st_mode & 0o111:
            return str(candidate)
    return None


def inspect_server(client: str, executable: str, *, run=subprocess.run) -> bool:
    """确认是否存在同名正确配置；地址冲突时拒绝静默覆盖。"""
    client = _client(client)
    get_command = [executable, 'mcp', 'get', HYPER3D_MCP_NAME]
    current = run(get_command, capture_output=True, text=True, timeout=10, check=False)
    if current.returncode == 0:
        output = (current.stdout or '') + '\n' + (current.stderr or '')
        if HYPER3D_MCP_URL not in output:
            raise ValueError('已有 hyper3d MCP 地址不一致，请先人工确认，未自动覆盖')
        return True
    return False


def authorization_command(client: str, executable: str, *, configured: bool) -> list[str]:
    """生成单个交互命令；add 本身可能直接进入 OAuth，必须后台执行。"""
    client = _client(client)
    if configured:
        return [executable, 'mcp', 'login', HYPER3D_MCP_NAME]
    if client == 'CODEX':
        return [executable, 'mcp', 'add', HYPER3D_MCP_NAME,
                '--url', HYPER3D_MCP_URL]
    return [executable, 'mcp', 'add', '--transport', 'http',
            HYPER3D_MCP_NAME, '--scope', 'user', HYPER3D_MCP_URL]


def authorization_commands(client: str, executable: str, *, configured: bool) -> list[list[str]]:
    """构造完整授权序列；缺失配置时必须先添加，再显式登录。"""
    first = authorization_command(client, executable, configured=configured)
    if configured:
        return [first]
    return [first, [executable, 'mcp', 'login', HYPER3D_MCP_NAME]]


def authorization_url(line: str) -> str | None:
    """只接受 Hyper3D 官方 OAuth 授权 URL，避免打开 CLI 输出中的任意链接。"""
    for match in _AUTHORIZATION_URL.finditer(str(line)):
        candidate = match.group(0).rstrip('.,;)]}')
        parsed = urlparse(candidate)
        if (parsed.scheme == 'https' and parsed.hostname == 'api.hyper3d.com'
                and parsed.path == '/api/grant/oauth/authorize'):
            return candidate
    return None


class AuthorizationRunner:
    """后台顺序执行客户端配置与 OAuth 登录，并打开官方授权页。"""

    def __init__(self, commands, *, popen=subprocess.Popen, open_url=webbrowser.open):
        self._commands = [list(command) for command in commands]
        self._popen = popen
        self._open_url = open_url
        self._process = None
        self._returncode = None
        self._cancelled = False
        self._thread = threading.Thread(target=self._run, name='partme-hyper3d-oauth', daemon=True)

    def start(self):
        self._thread.start()
        return self

    def poll(self):
        return None if self._thread.is_alive() else self._returncode

    @property
    def returncode(self):
        return self.poll()

    def terminate(self):
        self._cancelled = True
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def _run(self):
        for command in self._commands:
            if self._cancelled:
                self._returncode = 130
                return
            try:
                self._process = self._popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    close_fds=True,
                )
                opened = False
                for line in self._process.stdout or ():
                    url = authorization_url(line)
                    if url is not None and not opened:
                        self._open_url(url)
                        opened = True
                code = self._process.wait()
            except (OSError, subprocess.SubprocessError):
                self._returncode = 1
                return
            if code != 0:
                self._returncode = code
                return
        self._returncode = 0


def start_authorization(client: str, executable: str, *, configured: bool,
                        popen=subprocess.Popen, open_url=webbrowser.open) -> AuthorizationRunner:
    """启动完整授权序列；OAuth 凭据仍只由所选客户端保管。"""
    commands = authorization_commands(client, executable, configured=configured)
    return AuthorizationRunner(commands, popen=popen, open_url=open_url).start()


def inspect_client(client: str, executable: str, *, run=subprocess.run) -> dict:
    """只读取 CLI 状态；不解析或回显 OAuth Token。"""
    client = _client(client)
    if client == 'CODEX':
        command = [executable, 'mcp', 'list', '--json']
    else:
        command = [executable, 'mcp', 'get', HYPER3D_MCP_NAME]
    result = run(command, capture_output=True, text=True, timeout=10, check=False)
    if result.returncode != 0:
        return {'state': 'missing', 'statusText': '客户端未配置 Hyper3D MCP'}
    if client == 'CODEX':
        try:
            servers = json.loads(result.stdout or '[]')
        except (TypeError, json.JSONDecodeError):
            return {'state': 'error', 'statusText': '客户端 MCP 状态响应无效'}
        server = next((item for item in servers
                       if isinstance(item, dict) and item.get('name') == HYPER3D_MCP_NAME), None)
        if server is None:
            return {'state': 'missing', 'statusText': '客户端未配置 Hyper3D MCP'}
        transport = server.get('transport') if isinstance(server.get('transport'), dict) else {}
        if transport.get('url') != HYPER3D_MCP_URL:
            return {'state': 'error', 'statusText': '客户端 Hyper3D MCP 地址不一致'}
        auth_status = server.get('auth_status')
        if auth_status == 'o_auth':
            return {'state': 'authorized', 'statusText': '客户端 OAuth 已授权'}
        if auth_status == 'not_logged_in':
            return {'state': 'not_authorized', 'statusText': '等待浏览器授权'}
        return {'state': 'unknown', 'statusText': '已配置；授权状态待检测'}
    output = ((result.stdout or '') + '\n' + (result.stderr or '')).lower()
    if HYPER3D_MCP_NAME not in output:
        return {'state': 'missing', 'statusText': '客户端未配置 Hyper3D MCP'}
    if HYPER3D_MCP_URL.lower() not in output:
        return {'state': 'error', 'statusText': '客户端 Hyper3D MCP 地址不一致'}
    unauthorized = ('not logged in', 'needs authentication', 'not authenticated',
                    'authentication required', '未登录', '未授权')
    if any(token in output for token in unauthorized):
        return {'state': 'not_authorized', 'statusText': '等待浏览器授权'}
    authorized = (' oauth' in output or 'authenticated' in output or 'connected' in output
                  or '✓' in output)
    return ({'state': 'authorized', 'statusText': '客户端 OAuth 已授权'} if authorized else
            {'state': 'unknown', 'statusText': '已配置；授权状态待检测'})


def sync_preferences(preferences, *, find=find_client, inspect=inspect_client) -> dict:
    """把客户端真实 OAuth 状态同步到 Blender 偏好，但不读取任何 Token。"""
    if getattr(preferences, 'hyper3d_auth_mode', 'API_KEY') != 'MCP_OAUTH':
        return {'state': 'not_applicable', 'statusText': '当前使用 API Key'}
    client = getattr(preferences, 'hyper3d_oauth_client', 'CODEX')
    executable = find(client)
    if executable is None:
        status = {'state': 'missing', 'statusText': '未找到所选客户端 CLI'}
    else:
        try:
            status = inspect(client, executable)
        except (OSError, subprocess.SubprocessError, ValueError):
            status = {'state': 'error', 'statusText': '无法检测客户端授权状态'}
    preferences.hyper3d_oauth_status = {
        'authorized': 'AUTHORIZED',
        'not_authorized': 'NOT_AUTHORIZED',
        'missing': 'NOT_AUTHORIZED',
    }.get(status.get('state'), 'ERROR')
    return status


def _client(value: str) -> str:
    value = str(value).upper()
    if value not in SUPPORTED_CLIENTS:
        raise ValueError('仅支持 Codex 或 Claude Code 客户端 OAuth')
    return value
