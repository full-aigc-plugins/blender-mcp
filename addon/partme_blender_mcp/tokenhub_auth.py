"""由 THCLI 独占凭证的 TokenHub OAuth 适配边界。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def find_thcli(configured: str = "") -> str | None:
    """解析可执行文件；不搜索或读取 THCLI 的凭证目录。"""
    candidate = str(configured or "").strip()
    if candidate:
        path = Path(candidate).expanduser()
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which("thcli")


def _args(executable: str, profile: str, site: str, *command: str) -> list[str]:
    selected_profile = str(profile or "default").strip() or "default"
    selected_site = str(site or "cn").strip().lower()
    if selected_site not in {"cn", "intl"}:
        raise ValueError("TokenHub 站点必须为 cn 或 intl")
    return [executable, "--profile", selected_profile, "--site", selected_site, *command]


def inspect_status(executable: str | None, *, profile: str = "default", site: str = "cn",
                   runner=subprocess.run) -> dict:
    """只用退出码判断授权；命令输出永不进入返回值、日志或 Blender 状态。"""
    if not executable:
        return {"state": "missing", "statusText": "未安装 TokenHub CLI",
                "profile": profile, "site": site}
    try:
        result = runner(
            _args(executable, profile, site, "--json", "auth", "status"),
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"state": "error", "statusText": "TokenHub CLI 状态检测失败",
                "profile": profile, "site": site}
    if result.returncode == 0:
        state, text = "authorized", "TokenHub OAuth 已授权"
    else:
        state, text = "not_authorized", "TokenHub OAuth 未授权或已失效"
    return {"state": state, "statusText": text, "profile": profile, "site": site}


def start_authorization(executable: str, *, profile: str = "default", site: str = "cn",
                        directory: Path | None = None, popen=subprocess.Popen):
    """后台启动官方浏览器登录，并以私有日志维持 loopback 回调进程。"""
    root = Path(directory or tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    descriptor, log_path = tempfile.mkstemp(prefix="partme-tokenhub-auth-", suffix=".log", dir=root)
    os.chmod(log_path, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        process = popen(
            _args(executable, profile, site, "auth", "login"),
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            shell=False, start_new_session=True,
        )
    return process, Path(log_path)


def sync_preferences(preferences) -> dict:
    """刷新非敏感状态；不把 THCLI 输出复制到 RNA 属性。"""
    executable = find_thcli(getattr(preferences, "hunyuan3d_tokenhub_cli", ""))
    status = inspect_status(
        executable,
        profile=getattr(preferences, "hunyuan3d_tokenhub_profile", "default"),
        site=getattr(preferences, "hunyuan3d_tokenhub_site", "cn"),
    )
    preferences.hunyuan3d_tokenhub_status = {
        "missing": "MISSING", "authorized": "AUTHORIZED",
        "not_authorized": "NOT_AUTHORIZED", "error": "ERROR",
    }[status["state"]]
    return status
