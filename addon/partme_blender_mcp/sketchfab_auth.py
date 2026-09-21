"""Sketchfab OAuth 2.0 authorization-code flow with a loopback callback."""
from __future__ import annotations

import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


AUTHORIZE_URL = "https://sketchfab.com/oauth2/authorize/"
TOKEN_URL = "https://sketchfab.com/oauth2/token/"


def validate_redirect_uri(value: str) -> tuple[str, int, str]:
    parsed = urlparse(str(value).strip())
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.port is None or not parsed.path.startswith("/")):
        raise ValueError("Sketchfab OAuth 回调必须是带端口的本机 HTTP 地址")
    return parsed.hostname, parsed.port, parsed.path


def authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    if not str(client_id).strip():
        raise ValueError("Sketchfab OAuth Client ID 未配置")
    validate_redirect_uri(redirect_uri)
    return AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id.strip(),
        "redirect_uri": redirect_uri.strip(), "state": state,
    })


def _validate_token_payload(payload: dict) -> dict:
    if (not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str)
            or not payload["access_token"] or str(payload.get("token_type", "Bearer")).lower() != "bearer"):
        raise ValueError("Sketchfab OAuth Token 响应无效")
    return payload


def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str,
                  *, opener=urlopen) -> dict:
    if not client_secret:
        raise ValueError("Sketchfab OAuth Client Secret 未配置")
    body = urlencode({
        "grant_type": "authorization_code", "client_id": client_id,
        "client_secret": client_secret, "redirect_uri": redirect_uri, "code": code,
    }).encode("utf-8")
    request = Request(TOKEN_URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json",
    })
    with opener(request, timeout=30) as response:
        return _validate_token_payload(json.loads(response.read().decode("utf-8")))


def apply_token_response(preferences, payload: dict, *, now=time.time) -> None:
    payload = _validate_token_payload(payload)
    current = now() if callable(now) else float(now)
    preferences.sketchfab_access_token = payload["access_token"]
    if isinstance(payload.get("refresh_token"), str) and payload["refresh_token"]:
        preferences.sketchfab_refresh_token = payload["refresh_token"]
    preferences.sketchfab_token_expires_at = current + max(0, int(payload.get("expires_in", 0)))
    preferences.sketchfab_oauth_status = "AUTHORIZED"


def refresh_access_token(preferences, *, http, now=time.time) -> str:
    current = now() if callable(now) else float(now)
    if (preferences.sketchfab_access_token
            and (not preferences.sketchfab_token_expires_at
                 or preferences.sketchfab_token_expires_at > current + 60)):
        return preferences.sketchfab_access_token
    if not preferences.sketchfab_refresh_token:
        raise ValueError("Sketchfab OAuth 已过期，请重新授权")
    response = http.post(TOKEN_URL, data={
        "grant_type": "refresh_token", "client_id": preferences.sketchfab_client_id,
        "client_secret": preferences.sketchfab_client_secret,
        "refresh_token": preferences.sketchfab_refresh_token,
    }, timeout=(5, 30), allow_redirects=False)
    if response.status_code != 200:
        raise ValueError("Sketchfab OAuth 刷新失败，请重新授权")
    apply_token_response(preferences, response.json(), now=current)
    return preferences.sketchfab_access_token


def success_page(success: bool, message: str) -> bytes:
    color = "#63d238" if success else "#f2a93b"
    title = "Sketchfab 授权成功" if success else "Sketchfab 授权未完成"
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#16181d;color:#f4f6fa;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{width:min(460px,calc(100% - 40px));padding:48px 42px;text-align:center;background:#23262d;border:1px solid #363a44;border-radius:18px;box-shadow:0 24px 70px rgba(0,0,0,.38)}}.mark{{width:70px;height:70px;display:grid;place-items:center;margin:0 auto 24px;border-radius:50%;background:{color};color:#13200d;font-size:40px}}h1{{margin:0 0 14px}}p{{color:#b8bec9;line-height:1.7}}</style><body><main><div class="mark">{'✓' if success else '!'}</div><h1>{title}</h1><p>{message}</p></main></body></html>'''.encode("utf-8")


class AuthorizationRunner:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str,
                 *, open_url=webbrowser.open, exchange=exchange_code):
        self.client_id, self.client_secret, self.redirect_uri = client_id, client_secret, redirect_uri
        self.open_url, self.exchange = open_url, exchange
        self.state = secrets.token_urlsafe(32)
        self.result = None
        self.error = None
        self._done = False
        self._server = None
        self._thread = threading.Thread(target=self._run, name="partme-sketchfab-oauth", daemon=True)

    def start(self):
        self._thread.start()
        return self

    def poll(self):
        return 0 if self._done and self.error is None else 1 if self._done else None

    @property
    def returncode(self):
        return self.poll()

    def terminate(self):
        self.error = "授权已取消"
        if self._server is not None:
            self._server.shutdown()
        self._done = True

    def _run(self):
        host, port, path = validate_redirect_uri(self.redirect_uri)
        runner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                valid = parsed.path == path and query.get("state", [""])[0] == runner.state
                code = query.get("code", [""])[0] if valid else ""
                try:
                    if not code:
                        raise ValueError("回调地址或 state 校验失败")
                    runner.result = runner.exchange(
                        runner.client_id, runner.client_secret, runner.redirect_uri, code)
                    body, status = success_page(True, "可以关闭此页面并返回 Blender。"), 200
                except Exception as exc:
                    runner.error = str(exc)
                    body, status = success_page(False, "请返回 Blender 检查配置并重试。"), 400
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                runner._done = True
            def log_message(self, _format, *_args):
                return

        try:
            self._server = HTTPServer((host, port), Handler)
            self._server.timeout = 180
            self.open_url(authorization_url(self.client_id, self.redirect_uri, self.state))
            self._server.handle_request()
            if not self._done:
                self.error, self._done = "Sketchfab OAuth 授权超时", True
        except Exception as exc:
            self.error, self._done = str(exc), True
        finally:
            if self._server is not None:
                self._server.server_close()


def start_authorization(client_id: str, client_secret: str, redirect_uri: str) -> AuthorizationRunner:
    authorization_url(client_id, redirect_uri, "validation")
    if not client_secret:
        raise ValueError("Sketchfab OAuth Client Secret 未配置")
    return AuthorizationRunner(client_id, client_secret, redirect_uri).start()
