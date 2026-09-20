"""Non-blocking lifecycle manager for official SDK remote MCP listeners."""

from __future__ import annotations

import os
import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse


_TRANSPORTS = {"streamable-http", "sse"}
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _alive(process) -> bool:
    return process is not None and process.poll() is None


def _port_open(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        with socket.create_connection((probe_host, port), timeout=0.15):
            return True
    except OSError:
        return False


class RemoteListenerManager:
    """Own HTTP and SSE as separate child processes so either can stop alone."""

    def __init__(self, *, process_factory=subprocess.Popen, clock=time.monotonic):
        self._process_factory = process_factory
        self._clock = clock
        self._entries = {}
        self._stdio = {"state": "unknown", "statusText": "未探测", "message": ""}

    def _command(self, preferences, transport: str) -> tuple[list[str], dict, Path, Path]:
        self.validate(preferences, transport)
        python = Path(preferences.mcp_python or "").expanduser()
        if not python.is_file():
            raise ValueError("请先在远程设置中选择安装了官方 MCP SDK 的 Python")
        entrypoint = Path(preferences.mcp_entrypoint).expanduser() if preferences.mcp_entrypoint else None
        if entrypoint is not None and not entrypoint.is_file():
            raise ValueError("MCP 服务入口不存在")
        command = [str(python)]
        if entrypoint is None:
            command += ["-m", "partme_blender_mcp"]
        else:
            command.append(str(entrypoint))
        command += [
            "serve-remote", transport,
            "--host", preferences.remote_host,
            "--port", str(preferences.http_port if transport == "streamable-http" else preferences.sse_port),
            "--public-url", self.address(preferences, transport),
        ]
        if preferences.issuer_url:
            command += ["--issuer-url", preferences.issuer_url]
        if transport == "streamable-http":
            command += ["--streamable-http-path", preferences.http_path]
        else:
            command += ["--sse-path", preferences.sse_path, "--message-path", preferences.message_path]
        if preferences.tls_certfile and preferences.tls_keyfile:
            command += ["--tls-certfile", bpy_path(preferences.tls_certfile),
                        "--tls-keyfile", bpy_path(preferences.tls_keyfile)]
        env = dict(os.environ)
        if preferences.remote_token:
            env["PARTME_BLENDER_REMOTE_TOKEN"] = preferences.remote_token
        package_parent = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_parent, env.get("PYTHONPATH")]))
        log = Path(tempfile.gettempdir()) / "partme-blender" / f"remote-{transport}.log"
        status = Path(tempfile.gettempdir()) / "partme-blender" / f"remote-{transport}.json"
        command += ["--status-file", str(status)]
        return command, env, log, status

    @staticmethod
    def validate(preferences, transport: str) -> None:
        """Mirror server-side safety checks so Blender reports errors before spawn."""
        if transport not in _TRANSPORTS:
            raise ValueError("未知的远程传输")
        port = preferences.http_port if transport == "streamable-http" else preferences.sse_port
        if not 1 <= int(port) <= 65535:
            raise ValueError("远程端口必须在 1 到 65535 之间")
        paths = [preferences.http_path] if transport == "streamable-http" else [
            preferences.sse_path, preferences.message_path,
        ]
        if any(not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path
               for path in paths):
            raise ValueError("远程路径必须是以 / 开头的绝对 URL 路径")
        if transport == "sse" and not preferences.message_path.endswith("/"):
            raise ValueError("SSE 消息路径必须以 / 结尾")
        if bool(preferences.tls_certfile) != bool(preferences.tls_keyfile):
            raise ValueError("TLS 证书和私钥必须同时配置")
        if preferences.remote_host not in _LOOPBACK_HOSTS:
            if not preferences.remote_token:
                raise ValueError("非本机监听必须配置 Bearer Token")
            if not preferences.issuer_url:
                raise ValueError("非本机监听必须配置 OAuth Issuer URL")
            if urlparse(preferences.public_base_url or "").scheme.lower() != "https":
                raise ValueError("非本机监听必须配置 HTTPS 公网地址")

    @staticmethod
    def address(preferences, transport: str) -> str:
        if transport == "streamable-http":
            path, port = preferences.http_path, preferences.http_port
        else:
            path, port = preferences.sse_path, preferences.sse_port
        public = (preferences.public_base_url or "").rstrip("/")
        if public:
            return public + path
        scheme = "https" if preferences.tls_certfile and preferences.tls_keyfile else "http"
        host = preferences.remote_host
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        return f"{scheme}://{host}:{port}{path}"

    def start(self, preferences, transport: str, *, descriptor_path: Path | None = None) -> dict:
        if transport not in _TRANSPORTS:
            raise ValueError("unknown remote transport")
        current = self._entries.get(transport)
        if current and _alive(current["process"]):
            return self.snapshot(preferences, transport)
        command, env, log_path, status_path = self._command(preferences, transport)
        if descriptor_path is not None:
            # 每个窗口的监听器固定连接该窗口，不能自动发现到其他 Blender 会话。
            descriptor_path = Path(descriptor_path).resolve()
            env["PARTME_BLENDER_DESCRIPTOR"] = str(descriptor_path)
            log_path = descriptor_path.with_name(f"{descriptor_path.stem}-{transport}.log")
            status_path = descriptor_path.with_name(f"{descriptor_path.stem}-{transport}-status.json")
            command[command.index("--status-file") + 1] = str(status_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.unlink(missing_ok=True)
        log_stream = log_path.open("ab", buffering=0)
        try:
            process = self._process_factory(
                command, stdin=subprocess.DEVNULL, stdout=log_stream, stderr=subprocess.STDOUT,
                env=env, cwd=str(Path(__file__).resolve().parents[1]), start_new_session=os.name != "nt",
            )
        except Exception:
            log_stream.close()
            raise
        self._entries[transport] = {
            "process": process, "log": log_stream, "logPath": log_path, "statusPath": status_path,
            "state": "starting", "startedAt": self._clock(), "message": "",
        }
        return self.snapshot(preferences, transport)

    def stop(self, preferences, transport: str) -> dict:
        entry = self._entries.get(transport)
        if not entry or not _alive(entry["process"]):
            self._close_entry(transport)
            return self.snapshot(preferences, transport)
        entry["process"].terminate()
        entry["state"] = "stopping"
        entry["stoppedAt"] = self._clock()
        return self.snapshot(preferences, transport)

    def _close_entry(self, transport: str) -> None:
        entry = self._entries.pop(transport, None)
        if entry and entry.get("log"):
            entry["log"].close()
        if entry and entry.get("statusPath"):
            entry["statusPath"].unlink(missing_ok=True)

    def poll(self, preferences) -> float | None:
        pending = False
        active = False
        for transport, entry in list(self._entries.items()):
            process = entry["process"]
            if process.poll() is not None:
                if entry["state"] in {"stopped", "error"}:
                    continue
                code = process.returncode
                if entry.get("log"):
                    entry["log"].close()
                entry["log"] = None
                entry["state"] = "stopped" if code == 0 or entry["state"] == "stopping" else "error"
                # 子进程日志不是用户提示；正常关闭必须清空摘要。
                entry["message"] = (
                    f"监听器异常退出（代码 {code}）；请查看诊断日志"
                    if entry["state"] == "error" else ""
                )
                continue
            active = True
            port = preferences.http_port if transport == "streamable-http" else preferences.sse_port
            if entry["state"] == "starting":
                if _port_open(preferences.remote_host, port):
                    entry["state"] = "running"
                elif self._clock() - entry["startedAt"] > 8:
                    process.terminate()
                    entry["state"] = "error"
                    entry["message"] = "监听器启动超时；请检查端口、SDK、鉴权与 TLS 配置"
                else:
                    pending = True
            elif entry["state"] == "stopping":
                if self._clock() - entry["stoppedAt"] > 5:
                    process.kill()
                pending = True
        return 0.25 if pending else (1.0 if active else None)

    def snapshot(self, preferences, transport: str) -> dict:
        entry = self._entries.get(transport)
        state = entry["state"] if entry else "stopped"
        configuration_message = ""
        if entry is None:
            try:
                self.validate(preferences, transport)
            except ValueError as exc:
                state = "configuration_required"
                configuration_message = str(exc)
        status = {
            "starting": "启动中", "running": "运行中", "stopping": "停止中",
            "stopped": "已关闭", "error": "错误", "configuration_required": "需要配置",
        }[state]
        clients = 0
        if entry and entry.get("statusPath"):
            try:
                clients = int(json.loads(entry["statusPath"].read_text(encoding="utf-8")).get("clients", 0))
            except (OSError, ValueError, TypeError):
                clients = 0
        return {
            "transport": transport,
            "state": state,
            "statusText": status,
            "running": state in {"starting", "running", "stopping"},
            "address": self.address(preferences, transport),
            "clients": max(0, clients),
            "message": entry.get("message", "") if entry else configuration_message,
            "logPath": str(entry["logPath"]) if entry else "",
            "pid": entry["process"].pid if entry and _alive(entry["process"]) else None,
        }

    def probe_stdio(self, preferences) -> dict:
        try:
            python = Path(preferences.mcp_python or "").expanduser()
            if not python.is_file():
                raise ValueError("未配置 MCP Python")
            env = dict(os.environ)
            package_parent = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_parent, env.get("PYTHONPATH")]))
            result = subprocess.run(
                [str(python), "-c", "import mcp, partme_blender_mcp; print('ready')"],
                # A newly installed venv may spend several seconds warming the
                # official SDK's import caches.  Keep the probe bounded, but do
                # not turn that one-time cold start into a false "unavailable".
                env=env, capture_output=True, text=True, timeout=8, check=False,
            )
            if result.returncode:
                details = (result.stderr or result.stdout or "").strip()
                if "No module named 'mcp'" in details or 'No module named "mcp"' in details:
                    raise ValueError("官方 MCP SDK 未安装；请在远程设置中选择已安装 SDK 的 MCP Python")
                if "No module named 'partme_blender_mcp'" in details or 'No module named "partme_blender_mcp"' in details:
                    raise ValueError("PartMe MCP 运行时未安装；请安装发布包或重新选择 MCP Python")
                last_line = next((line.strip() for line in reversed(details.splitlines()) if line.strip()), "")
                raise ValueError("MCP Python 探测失败" + (f"：{last_line[:160]}" if last_line else ""))
            self._stdio = {"state": "ready", "statusText": "已就绪", "message": ""}
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            self._stdio = {"state": "unavailable", "statusText": "不可用", "message": str(exc)}
        return dict(self._stdio)

    def stdio_snapshot(self) -> dict:
        return dict(self._stdio)

    def shutdown(self) -> None:
        for transport in tuple(self._entries):
            entry = self._entries[transport]
            if _alive(entry["process"]):
                entry["process"].terminate()
            self._close_entry(transport)


def bpy_path(value: str) -> str:
    try:
        import bpy
        return bpy.path.abspath(value)
    except ImportError:
        return str(Path(value).expanduser())


_MANAGER = RemoteListenerManager()


def manager() -> RemoteListenerManager:
    return _MANAGER
