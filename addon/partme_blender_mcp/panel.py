"""Visible, provider-aware PartMe Blender MCP workbench in Blender's 3D View sidebar."""

import json
import os
import secrets
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import bpy

from . import runtime


_EXECUTION_MODES = [
    ("interactive", "Interactive", "Review milestones"),
    ("auto_with_budget", "Automatic local design", "Complete the authorized local task"),
    ("review_only", "Read only", "Inspect without changing scene content or exporting"),
]
_ASSET_STRATEGIES = [
    ("auto_search_generate", "自动搜索与生成", "优先搜索资产库，缺失时在授权预算内自动生成"),
    ("search_only", "仅搜索素材", "只搜索素材库，不调用 AI 生成模型"),
    ("disabled", "不使用外部素材", "不搜索或生成外部素材"),
]
_TABS = [
    ("WORK", "制作", "制作会话、审批和快捷操作"),
    ("ASSETS", "素材", "资产与素材库"),
    ("MODELS", "模型", "AI 生成模型"),
    ("ACCESS", "接入", "本地与远程 MCP 接入"),
]
_PROVIDER_SYNC_MAX_ATTEMPTS = 3
# 断点使用 View2D 内容坐标，不能直接使用屏幕帧缓冲宽度。
_COMPACT_REGION_WIDTH = 360
_provider_sync_attempts = 0
_status_previews = None
_playback_snapshot = {}
_hyper3d_oauth_process = None


def _refresh_playback_ui():
    """主线程定时检查播放状态；只重绘制作页且仅在状态变化时重绘。"""
    global _playback_snapshot
    wm = bpy.context.window_manager
    current = {}
    if wm and getattr(wm, "partme_blender_ui_tab", None) == "WORK":
        for window in wm.windows:
            screen = window.screen
            if screen is None or window.scene is None:
                continue
            key = window.as_pointer()
            state = (screen.is_animation_playing, window.scene.frame_current)
            current[key] = state
            if _playback_snapshot.get(key) != state:
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
    _playback_snapshot = current
    return 0.1


def _sidebar_width(context):
    """以 View2D 坐标计算内容宽度，适配侧栏缩放和 Retina。"""
    region = context.region
    try:
        left = region.view2d.region_to_view(0, 0)[0]
        right = region.view2d.region_to_view(region.width, 0)[0]
        scale = max(0.5, context.preferences.system.ui_scale)
        return max(120, abs(right - left) / scale - 16)
    except AttributeError:
        return max(120, region.width - 32)


def _small_actions(row, units=2.0):
    """辅助操作按内容靠右收缩，避免抢占名称和状态的宽度。"""
    actions = row.row(align=True)
    actions.alignment = "RIGHT"
    actions.ui_units_x = units
    return actions


def _wrapped_label(layout, context, text, icon="NONE"):
    """按可见宽度换行中英文说明，保留完整错误和权限提示。"""
    budget = max(12, int((_sidebar_width(context) - 24) / 7))
    lines, line, size = [], "", 0
    for char in str(text):
        width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if char == "\n" or (line and size + width > budget):
            lines.append(line)
            line, size = "", 0
        if char != "\n":
            line += char
            size += width
    if line:
        lines.append(line)
    column = layout.column(align=True)
    for index, line in enumerate(lines):
        column.label(text=line, icon=icon if index == 0 else "NONE")


def _register_status_icons():
    """Load the V4 status palette without creating saveable Blender datablocks."""
    global _status_previews
    if _status_previews is not None:
        return
    import bpy.utils.previews

    previews = bpy.utils.previews.new()
    icon_root = Path(__file__).with_name("icons")
    for state in ("ready", "ready_check", "busy", "configuration_required", "disabled", "error"):
        previews.load(state, str(icon_root / f"status_{state}.png"), "IMAGE")
    _status_previews = previews


def _unregister_status_icons():
    global _status_previews
    if _status_previews is None:
        return
    import bpy.utils.previews

    bpy.utils.previews.remove(_status_previews)
    _status_previews = None


def _status_icon_value(state: str) -> int:
    palette_state = {
        "running": "ready", "completed": "ready",
        "starting": "busy", "stopping": "busy",
        "stopped": "disabled", "unavailable": "disabled", "cancelled": "disabled",
    }.get(state, state)
    if _status_previews is None or palette_state not in _status_previews:
        return 0
    return _status_previews[palette_state].icon_id


def _default_mcp_python():
    explicit = os.environ.get("PARTME_BLENDER_MCP_PYTHON")
    if explicit:
        return explicit
    try:
        from .harness.version import __version__
        if sys.platform == "darwin":
            installed = Path.home() / "Library/Application Support/PartMe/BlenderMCP" / __version__ / "venv/bin/python"
        elif os.name == "nt":
            installed = Path(os.environ.get("LOCALAPPDATA", "")) / "PartMe/BlenderMCP" / __version__ / "venv/Scripts/python.exe"
        else:
            installed = Path.home() / ".local/share/PartMe/BlenderMCP" / __version__ / "venv/bin/python"
        if installed.is_file():
            return str(installed)
    except Exception:
        pass
    return shutil.which("python3") or ""


def _poll_remote_listeners():
    preferences = _addon_preferences(bpy.context)
    if preferences is None:
        return None
    from .remote import manager
    return manager().poll(preferences)


def _auto_start_remote(context):
    preferences = _addon_preferences(context)
    if preferences is None:
        return
    from .remote import manager
    for transport, enabled in (
        ("streamable-http", preferences.remote_auto_start_http),
        ("sse", preferences.remote_auto_start_sse),
    ):
        if enabled and not manager().snapshot(preferences, transport)["running"]:
            manager().start(preferences, transport, descriptor_path=runtime.current().descriptor_path)
    if any((preferences.remote_auto_start_http, preferences.remote_auto_start_sse)):
        if not bpy.app.timers.is_registered(_poll_remote_listeners):
            bpy.app.timers.register(_poll_remote_listeners, first_interval=0.1)


def _addon_preferences(context):
    addon = getattr(getattr(context, "preferences", None), "addons", {}).get(__package__)
    return getattr(addon, "preferences", None)


def _enabled_preferences(context) -> dict[str, bool]:
    preferences = _addon_preferences(context)
    if preferences is None:
        return {}
    try:
        payload = json.loads(preferences.provider_enabled_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return {key: value for key, value in payload.items() if isinstance(key, str) and type(value) is bool}


def _save_enabled_preference(context, provider_id: str, enabled: bool) -> None:
    preferences = _addon_preferences(context)
    if preferences is None:
        return
    payload = _enabled_preferences(context)
    payload[provider_id] = enabled
    preferences.provider_enabled_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sync_polypizza_key(context) -> None:
    preferences = _addon_preferences(context)
    if preferences is not None and preferences.polypizza_api_key:
        os.environ["POLYPIZZA_API_KEY"] = preferences.polypizza_api_key


def _sync_hyper3d_oauth(context) -> None:
    """Refresh OAuth readiness from the selected client without reading its token."""
    preferences = _addon_preferences(context)
    if preferences is None or preferences.hyper3d_auth_mode != "MCP_OAUTH":
        return
    if _hyper3d_oauth_process is not None and _hyper3d_oauth_process.poll() is None:
        return
    from .hyper3d_auth import sync_preferences
    sync_preferences(preferences)


def _apply_provider_preferences(context, *, refresh=True):
    from .harness.provider_registry import ProviderRegistryError, get_provider_registry

    _sync_polypizza_key(context)
    _sync_hyper3d_oauth(context)
    registry = get_provider_registry()
    if refresh:
        registry.refresh(context)
    stored = _enabled_preferences(context)
    for provider in registry.snapshot(context)["providers"]:
        if not provider["mutable"]:
            continue
        enabled = stored.get(provider["providerId"], provider["defaultEnabled"])
        try:
            registry.set_enabled(provider["providerId"], enabled, context=context)
        except ProviderRegistryError:
            continue
    return registry.snapshot(context)


def _deferred_provider_sync():
    """Apply provider preferences after Blender finishes enabling both Add-ons.

    Blender may recreate RNA-backed Scene property values while an Add-on is still
    inside its ``register`` call. A main-loop timer is therefore the authoritative
    initial synchronization point; file loads are covered independently by the
    persistent load handler in ``runtime.py``.
    """
    global _provider_sync_attempts
    _provider_sync_attempts += 1
    try:
        if getattr(bpy.context, "scene", None) is None:
            raise RuntimeError("Blender scene context is not ready")
        _apply_provider_preferences(bpy.context)
    except Exception as exc:
        if _provider_sync_attempts < _PROVIDER_SYNC_MAX_ATTEMPTS:
            return 0.25
        print(f"PartMe Blender MCP provider preference synchronization failed: {exc}")
    return None


def _update_polypizza_key(_preferences, context):
    preferences = _addon_preferences(context)
    if preferences is None:
        return
    if preferences.polypizza_api_key:
        os.environ["POLYPIZZA_API_KEY"] = preferences.polypizza_api_key
    else:
        os.environ.pop("POLYPIZZA_API_KEY", None)
    try:
        from .harness.provider_registry import get_provider_registry
        get_provider_registry().refresh(context)
    except Exception:
        pass


class PARTMEBLENDER_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    provider_enabled_json: bpy.props.StringProperty(default="{}", options={"HIDDEN"})
    sketchfab_api_key: bpy.props.StringProperty(name="Sketchfab API Key", subtype="PASSWORD")
    hyper3d_api_key: bpy.props.StringProperty(name="Rodin API Key", subtype="PASSWORD")
    hyper3d_auth_mode: bpy.props.EnumProperty(name="授权方式", default="MCP_OAUTH", items=(
        ("MCP_OAUTH", "客户端 OAuth（推荐）", "免费账户通过 Codex 或 Claude Code 浏览器授权"),
        ("API_KEY", "API Key", "开发者 API 使用 Bearer Key"),
    ))
    hyper3d_oauth_client: bpy.props.EnumProperty(name="授权客户端", default="CODEX", items=(
        ("CODEX", "Codex", "在 Codex 中配置 Hyper3D MCP"),
        ("CLAUDE", "Claude Code", "在 Claude Code 中配置 Hyper3D MCP"),
    ))
    hyper3d_oauth_status: bpy.props.EnumProperty(default="NOT_AUTHORIZED", options={"HIDDEN"}, items=(
        ("NOT_AUTHORIZED", "未授权", ""), ("AUTHORIZING", "授权中", ""),
        ("AUTHORIZED", "已授权", ""), ("ERROR", "授权失败", ""),
    ))
    hyper3d_mode: bpy.props.EnumProperty(items=(("MAIN_SITE", "hyper3d.ai", ""), ("FAL_AI", "fal.ai", "")))
    hunyuan3d_mode: bpy.props.EnumProperty(items=(("OFFICIAL_API", "腾讯云官方 API", ""), ("LOCAL_API", "本地 API", "")))
    hunyuan3d_secret_id: bpy.props.StringProperty(name="SecretId", subtype="PASSWORD")
    hunyuan3d_secret_key: bpy.props.StringProperty(name="SecretKey", subtype="PASSWORD")
    hunyuan3d_api_url: bpy.props.StringProperty(name="API URL")
    hunyuan3d_intl_pro: bpy.props.BoolProperty(name="国际站 Pro 账户")
    polypizza_api_key: bpy.props.StringProperty(
        name="Poly Pizza API Key",
        description="Stored in Blender user preferences; never written to the .blend or MCP receipts",
        subtype="PASSWORD",
        update=_update_polypizza_key,
    )
    mcp_python: bpy.props.StringProperty(
        name="MCP Python", subtype="FILE_PATH", default=_default_mcp_python(),
        description="安装了 partme-blender-mcp 与官方 MCP Python SDK 的外部 Python",
    )
    mcp_entrypoint: bpy.props.StringProperty(
        name="服务入口", subtype="FILE_PATH", default=os.environ.get("PARTME_BLENDER_MCP_ENTRYPOINT", ""),
        description="可选的插件服务脚本；留空时使用 python -m partme_blender_mcp",
    )
    remote_host: bpy.props.StringProperty(name="绑定主机", default="127.0.0.1")
    http_port: bpy.props.IntProperty(name="HTTP 端口", default=9877, min=1, max=65535)
    sse_port: bpy.props.IntProperty(name="SSE 端口", default=9878, min=1, max=65535)
    http_path: bpy.props.StringProperty(name="HTTP 路由", default="/mcp")
    sse_path: bpy.props.StringProperty(name="SSE 路由", default="/sse")
    message_path: bpy.props.StringProperty(name="SSE 消息路由", default="/messages/")
    public_base_url: bpy.props.StringProperty(name="公开基础地址", default="")
    issuer_url: bpy.props.StringProperty(name="OAuth Issuer", default="")
    remote_token: bpy.props.StringProperty(
        name="Bearer Token", subtype="PASSWORD",
        description="仅保存在 Blender 用户配置并通过子进程环境传递，不写入命令行、场景或回执",
    )
    tls_certfile: bpy.props.StringProperty(name="TLS 证书", subtype="FILE_PATH")
    tls_keyfile: bpy.props.StringProperty(name="TLS 私钥", subtype="FILE_PATH")
    remote_auto_start_http: bpy.props.BoolProperty(name="Blender 启动时开启 HTTP", default=False)
    remote_auto_start_sse: bpy.props.BoolProperty(name="Blender 启动时开启 SSE", default=False)

    def draw(self, _context):
        layout = self.layout
        layout.label(text="供应商凭证", icon="LOCKED")
        box = layout.box()
        box.label(text="Poly Pizza（PartMe 原生路径）")
        box.prop(self, "polypizza_api_key", text="API Key")
        box.label(text="凭证仅保存在本机 Blender 用户配置中", icon="INFO")
        layout.separator()
        layout.label(text="MCP 接入", icon="NETWORK_DRIVE")
        box = layout.box()
        box.prop(self, "mcp_python")
        box.prop(self, "mcp_entrypoint")
        box.prop(self, "remote_host")
        row = box.row(align=True)
        row.prop(self, "http_port")
        row.prop(self, "sse_port")
        box.prop(self, "http_path")
        box.prop(self, "sse_path")
        box.prop(self, "message_path")
        box.prop(self, "public_base_url")
        box.prop(self, "issuer_url")
        box.prop(self, "remote_token", text="Bearer Token")
        row = box.row(align=True)
        row.operator(PARTMEBLENDER_OT_configure_remote_token.bl_idname, text="配置 Token", icon="LOCKED")
        row.operator(PARTMEBLENDER_OT_generate_remote_token.bl_idname, text="生成新 Token", icon="FILE_REFRESH")
        row.operator(PARTMEBLENDER_OT_copy_remote_token.bl_idname, text="复制 Token", icon="COPYDOWN")
        box.prop(self, "tls_certfile")
        box.prop(self, "tls_keyfile")
        row = box.row(align=True)
        row.prop(self, "remote_auto_start_http")
        row.prop(self, "remote_auto_start_sse")
        box.label(text="非本机绑定必须配置 Token、OAuth Issuer 与 HTTPS 公开地址", icon="LOCKED")


class PARTMEBLENDER_OT_start(bpy.types.Operator):
    bl_idname = "partme_blender.start_connector"
    bl_label = "启动 MCP 服务"

    def execute(self, context):
        output_root = bpy.path.abspath(context.scene.partme_blender_output_root or "")
        if not output_root:
            self.report({"ERROR"}, "请先在执行设置中选择授权输出目录")
            return {"CANCELLED"}
        root = Path(output_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        asset_root = bpy.path.abspath(context.scene.partme_blender_asset_root or "")
        asset_roots = [Path(asset_root).resolve()] if asset_root else []
        from .harness.execution_policy import ExecutionPolicy
        policy = ExecutionPolicy.from_dict({
            "mode": context.scene.partme_blender_execution_mode,
            "approvedOutputRoot": str(root),
            "allowDesignedProxies": context.scene.partme_blender_allow_proxies,
            "assetStrategy": context.scene.partme_blender_asset_strategy,
        })
        try:
            handle = runtime.start(
                bpy, approved_output_root=root, approved_asset_roots=asset_roots, execution_policy=policy,
            )
            _apply_provider_preferences(context)
            _auto_start_remote(context)
        except Exception as exc:
            self.report({"ERROR"}, f"PartMe Blender MCP 启动失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"PartMe Blender MCP 已启动：{handle.descriptor_path}")
        return {"FINISHED"}


class PARTMEBLENDER_OT_revoke(bpy.types.Operator):
    bl_idname = "partme_blender.revoke_connector"
    bl_label = "撤销会话"

    def execute(self, _context):
        runtime.stop()
        self.report({"INFO"}, "PartMe Blender MCP 会话已撤销")
        return {"FINISHED"}


class PARTMEBLENDER_OT_approve_request(bpy.types.Operator):
    bl_idname = "partme_blender.approve_request"
    bl_label = "批准一次"
    request_id: bpy.props.StringProperty()

    def execute(self, _context):
        handle = runtime.current()
        if handle is None:
            self.report({"ERROR"}, "请先启动 MCP 服务")
            return {"CANCELLED"}
        try:
            handle.session.approve_pending(self.request_id)
        except Exception as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class PARTMEBLENDER_OT_deny_request(bpy.types.Operator):
    bl_idname = "partme_blender.deny_request"
    bl_label = "拒绝"
    request_id: bpy.props.StringProperty()

    def execute(self, _context):
        handle = runtime.current()
        if handle is None:
            self.report({"ERROR"}, "请先启动 MCP 服务")
            return {"CANCELLED"}
        try:
            handle.session.deny_pending(self.request_id)
        except Exception as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class PARTMEBLENDER_OT_refresh_providers(bpy.types.Operator):
    bl_idname = "partme_blender.refresh_providers"
    bl_label = "刷新状态"

    def execute(self, context):
        from .harness.provider_registry import reload_provider_registry
        try:
            reload_provider_registry(Path(__file__).with_name("providers.json"))
            snapshot = _apply_provider_preferences(context)
            preferences = _addon_preferences(context)
            if preferences is not None:
                from .remote import manager
                manager().probe_stdio(preferences)
                manager().poll(preferences)
        except Exception as exc:
            self.report({"WARNING"}, f"供应商目录无效：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已刷新 {snapshot['summary']['total']} 个供应商")
        return {"FINISHED"}


class PARTMEBLENDER_OT_set_provider_enabled(bpy.types.Operator):
    bl_idname = "partme_blender.set_provider_enabled"
    bl_label = "启用或停用供应商"
    provider_id: bpy.props.StringProperty()
    enabled: bpy.props.BoolProperty()

    def execute(self, context):
        from .harness.provider_registry import ProviderRegistryError, get_provider_registry
        registry = get_provider_registry()
        try:
            snapshot = registry.refresh(context)
            row = next((item for item in snapshot["providers"]
                        if item["providerId"] == self.provider_id), None)
            if (self.enabled and row is not None and row["configurable"]
                    and row["state"] == "configuration_required"):
                result = bpy.ops.partme_blender.provider_settings(
                    "INVOKE_DEFAULT", provider_id=self.provider_id, enable_after_save=True,
                )
                return {"CANCELLED"} if "CANCELLED" in result else {"FINISHED"}
            registry.set_enabled(self.provider_id, self.enabled, context=context)
            _save_enabled_preference(context, self.provider_id, self.enabled)
            bpy.ops.wm.save_userpref()
            snapshot = registry.refresh(context)
            row = next(item for item in snapshot["providers"] if item["providerId"] == self.provider_id)
        except ProviderRegistryError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{row['label']}：{row['statusText']}")
        return {"FINISHED"}


def _open_addon_preferences(module: str):
    bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
    try:
        bpy.context.preferences.active_section = "ADDONS"
        bpy.ops.preferences.addon_show(module=module)
    except (AttributeError, RuntimeError):
        pass


class PARTMEBLENDER_OT_hyper3d_oauth(bpy.types.Operator):
    bl_idname = "partme_blender.hyper3d_oauth"
    bl_label = "Hyper3D 浏览器授权"
    bl_description = "在所选客户端中配置 Hyper3D MCP，并通过浏览器 OAuth 授权"
    client: bpy.props.EnumProperty(items=(("CODEX", "Codex", ""),
                                          ("CLAUDE", "Claude Code", "")))
    _process = None
    _timer = None

    def invoke(self, context, _event):
        global _hyper3d_oauth_process
        if _hyper3d_oauth_process is not None and _hyper3d_oauth_process.poll() is None:
            self.report({"WARNING"}, "Hyper3D OAuth 授权正在进行")
            return {"CANCELLED"}
        from .hyper3d_auth import find_client, inspect_server, start_authorization
        executable = find_client(self.client)
        if executable is None:
            self.report({"ERROR"}, "未找到所选客户端 CLI；请先安装并启动 Codex 或 Claude Code")
            return {"CANCELLED"}
        try:
            configured = inspect_server(self.client, executable)
            self._process = start_authorization(
                self.client, executable, configured=configured)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _hyper3d_oauth_process = self._process
        preferences = _addon_preferences(context)
        preferences.hyper3d_auth_mode = "MCP_OAUTH"
        preferences.hyper3d_oauth_client = self.client
        preferences.hyper3d_oauth_status = "AUTHORIZING"
        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({"INFO"}, "请在浏览器中确认 Hyper3D 工作区与授权范围")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self._finish(context, cancelled=True)
            return {"CANCELLED"}
        if event.type != "TIMER" or self._process.poll() is None:
            return {"PASS_THROUGH"}
        return self._finish(context, cancelled=False)

    def _finish(self, context, *, cancelled):
        global _hyper3d_oauth_process
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if cancelled and self._process is not None and self._process.poll() is None:
            self._process.terminate()
        preferences = _addon_preferences(context)
        if cancelled:
            preferences.hyper3d_oauth_status = "NOT_AUTHORIZED"
            message = "已取消 Hyper3D OAuth 授权"
        else:
            from .hyper3d_auth import find_client, inspect_client
            executable = find_client(self.client)
            try:
                status = inspect_client(self.client, executable) if executable else {
                    "state": "missing", "statusText": "客户端不可用"}
            except (OSError, subprocess.SubprocessError):
                status = {"state": "error", "statusText": "无法检测客户端授权状态"}
            authorized = self._process.returncode == 0 and status["state"] == "authorized"
            preferences.hyper3d_oauth_status = "AUTHORIZED" if authorized else "ERROR"
            message = "Hyper3D OAuth 已授权" if authorized else status["statusText"]
        _hyper3d_oauth_process = None
        bpy.ops.wm.save_userpref()
        from .harness.provider_registry import get_provider_registry
        get_provider_registry().refresh(context)
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        self.report({"INFO" if preferences.hyper3d_oauth_status == "AUTHORIZED" else "WARNING"}, message)
        return {"FINISHED" if preferences.hyper3d_oauth_status == "AUTHORIZED" else "CANCELLED"}


class PARTMEBLENDER_OT_provider_settings(bpy.types.Operator):
    bl_idname = "partme_blender.provider_settings"
    bl_label = "配置供应商"
    provider_id: bpy.props.StringProperty()
    enable_after_save: bpy.props.BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})
    api_key: bpy.props.StringProperty(name="API Key", subtype="PASSWORD")
    hyper3d_auth_mode: bpy.props.EnumProperty(name="授权方式", items=(
        ("MCP_OAUTH", "客户端 OAuth（推荐）", "免费账户通过浏览器授权，不向 Blender 提供 Token"),
        ("API_KEY", "API Key", "使用 Hyper3D 或 fal.ai 开发者 API Key"),
    ))
    oauth_client: bpy.props.EnumProperty(name="授权客户端", items=(
        ("CODEX", "Codex", ""), ("CLAUDE", "Claude Code", ""),
    ))
    hyper3d_mode: bpy.props.EnumProperty(
        name="平台", items=(("MAIN_SITE", "hyper3d.ai", "hyper3d.ai"), ("FAL_AI", "fal.ai", "fal.ai")),
    )
    hunyuan3d_mode: bpy.props.EnumProperty(
        name="接入模式", items=(("LOCAL_API", "本地 API", "本地 Hunyuan3D API"),
                            ("OFFICIAL_API", "腾讯云官方 API", "腾讯云 Hunyuan3D API")),
    )
    secret_id: bpy.props.StringProperty(name="SecretId", subtype="PASSWORD")
    secret_key: bpy.props.StringProperty(name="SecretKey", subtype="PASSWORD")
    api_url: bpy.props.StringProperty(name="API URL")
    international_pro: bpy.props.BoolProperty(name="国际站 Pro 账户")

    def _provider_preferences(self, context):
        return _addon_preferences(context)

    def invoke(self, context, _event):
        preferences = _addon_preferences(context)
        community = self._provider_preferences(context)
        if self.provider_id == "polypizza" and preferences is not None:
            self.api_key = preferences.polypizza_api_key
        elif self.provider_id == "sketchfab" and community is not None:
            self.api_key = community.sketchfab_api_key
        elif self.provider_id == "hyper3d" and community is not None:
            self.api_key = community.hyper3d_api_key
            self.hyper3d_mode = community.hyper3d_mode
            self.hyper3d_auth_mode = community.hyper3d_auth_mode
            self.oauth_client = community.hyper3d_oauth_client
        elif self.provider_id == "hunyuan3d" and community is not None:
            self.hunyuan3d_mode = community.hunyuan3d_mode
            self.secret_id = community.hunyuan3d_secret_id
            self.secret_key = community.hunyuan3d_secret_key
            self.api_url = community.hunyuan3d_api_url
            self.international_pro = community.hunyuan3d_intl_pro
        else:
            self.report({"WARNING"}, "供应商配置不可用；请确认对应 Add-on 已启用")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(
            self, width=420, title="供应商配置",
            confirm_text="保存并启用" if self.enable_after_save else "保存",
        )

    def draw(self, _context):
        layout = self.layout
        layout.label(text={
            "polypizza": "Poly Pizza（PartMe 原生）",
            "sketchfab": "Sketchfab",
            "hyper3d": "Hyper3D Rodin",
            "hunyuan3d": "腾讯混元 3D",
        }.get(self.provider_id, "供应商"), icon="LOCKED")
        if self.provider_id in {"polypizza", "sketchfab"}:
            layout.prop(self, "api_key")
        elif self.provider_id == "hyper3d":
            layout.prop(self, "hyper3d_auth_mode")
            if self.hyper3d_auth_mode == "MCP_OAUTH":
                layout.prop(self, "oauth_client")
                layout.label(text="https://api.hyper3d.com/api/mcp", icon="URL")
                status = _addon_preferences(bpy.context).hyper3d_oauth_status
                layout.label(text={"AUTHORIZED": "客户端 OAuth 已授权",
                                   "AUTHORIZING": "等待浏览器授权",
                                   "ERROR": "授权失败，请重试"}.get(status, "尚未授权"),
                             icon="CHECKMARK" if status == "AUTHORIZED" else "INFO")
                action = layout.operator(PARTMEBLENDER_OT_hyper3d_oauth.bl_idname,
                                         text="重新授权" if status == "AUTHORIZED" else "浏览器授权",
                                         icon="URL")
                action.client = self.oauth_client
            else:
                layout.prop(self, "hyper3d_mode")
                layout.prop(self, "api_key")
        elif self.provider_id == "hunyuan3d":
            layout.prop(self, "hunyuan3d_mode")
            if self.hunyuan3d_mode == "OFFICIAL_API":
                layout.prop(self, "secret_id")
                layout.prop(self, "secret_key")
                layout.prop(self, "international_pro")
            else:
                layout.prop(self, "api_url")
        if self.provider_id != "hyper3d" or self.hyper3d_auth_mode == "API_KEY":
            layout.label(text="凭证仅保存在本机 Blender 用户配置中", icon="INFO")
        else:
            layout.label(text="OAuth Token 由客户端保管，不写入 Blender", icon="LOCKED")

    def execute(self, context):
        preferences = _addon_preferences(context)
        community = self._provider_preferences(context)
        if self.provider_id == "polypizza" and preferences is not None:
            preferences.polypizza_api_key = self.api_key.strip()
        elif self.provider_id == "sketchfab" and community is not None:
            community.sketchfab_api_key = self.api_key.strip()
        elif self.provider_id == "hyper3d" and community is not None:
            community.hyper3d_auth_mode = self.hyper3d_auth_mode
            community.hyper3d_oauth_client = self.oauth_client
            community.hyper3d_mode = self.hyper3d_mode
            community.hyper3d_api_key = self.api_key.strip()
        elif self.provider_id == "hunyuan3d" and community is not None:
            community.hunyuan3d_mode = self.hunyuan3d_mode
            community.hunyuan3d_secret_id = self.secret_id.strip()
            community.hunyuan3d_secret_key = self.secret_key.strip()
            community.hunyuan3d_api_url = self.api_url.strip()
            community.hunyuan3d_intl_pro = self.international_pro
        else:
            self.report({"WARNING"}, "供应商配置不可用")
            return {"CANCELLED"}
        from .harness.provider_registry import get_provider_registry
        registry = get_provider_registry()
        snapshot = registry.refresh(context)
        provider = next(row for row in snapshot["providers"] if row["providerId"] == self.provider_id)
        if self.enable_after_save and provider["state"] != "configuration_required":
            from .harness.provider_registry import ProviderRegistryError
            try:
                registry.set_enabled(self.provider_id, True, context=context)
            except ProviderRegistryError as exc:
                self.report({"WARNING"}, str(exc))
                return {"CANCELLED"}
            _save_enabled_preference(context, self.provider_id, True)
            snapshot = registry.refresh(context)
        bpy.ops.wm.save_userpref()
        provider = next(row for row in snapshot["providers"] if row["providerId"] == self.provider_id)
        self.report({"INFO"}, f"{provider['label']}：{provider['statusText']}")
        return {"FINISHED"}


class PARTMEBLENDER_OT_cancel_provider_task(bpy.types.Operator):
    bl_idname = "partme_blender.cancel_provider_task"
    bl_label = "终止生成"
    provider_id: bpy.props.StringProperty()
    task_id: bpy.props.StringProperty()

    def execute(self, _context):
        from .harness.provider_tasks import ProviderTaskError, get_provider_task_registry
        try:
            task = get_provider_task_registry().request_cancel(self.provider_id, self.task_id)
        except ProviderTaskError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"WARNING" if task["remoteMayContinue"] else "INFO"}, task["message"])
        return {"FINISHED"}


class PARTMEBLENDER_OT_execution_settings(bpy.types.Operator):
    bl_idname = "partme_blender.execution_settings"
    bl_label = "权限与执行"

    output_root: bpy.props.StringProperty(name="输出目录", subtype="DIR_PATH")
    asset_root: bpy.props.StringProperty(name="素材目录", subtype="DIR_PATH")
    execution_mode: bpy.props.EnumProperty(name="执行模式", items=_EXECUTION_MODES)
    asset_strategy: bpy.props.EnumProperty(name="素材策略", items=_ASSET_STRATEGIES)

    def invoke(self, context, _event):
        scene = context.scene
        self.output_root = scene.partme_blender_output_root
        self.asset_root = scene.partme_blender_asset_root
        self.execution_mode = scene.partme_blender_execution_mode
        self.asset_strategy = scene.partme_blender_asset_strategy
        return context.window_manager.invoke_props_dialog(
            self, width=420, title="权限与执行", confirm_text="保存并应用",
        )

    def draw(self, _context):
        layout = self.layout
        for name, label in (
            ("output_root", "输出目录"),
            ("asset_root", "素材目录"),
            ("execution_mode", "执行模式"),
            ("asset_strategy", "素材策略"),
        ):
            layout.label(text=label)
            layout.prop(self, name, text="")

    def execute(self, context):
        output_root = bpy.path.abspath(self.output_root or "")
        if not output_root:
            self.report({"ERROR"}, "输出目录不能为空")
            return {"CANCELLED"}
        root = Path(output_root).resolve()
        asset_root = bpy.path.abspath(self.asset_root or "")
        asset_roots = [Path(asset_root).resolve()] if asset_root else []
        from .harness.execution_policy import ExecutionPolicy
        try:
            policy = ExecutionPolicy.from_dict({
                "mode": self.execution_mode,
                "approvedOutputRoot": str(root),
                "allowDesignedProxies": context.scene.partme_blender_allow_proxies,
                "assetStrategy": self.asset_strategy,
            })
            root.mkdir(parents=True, exist_ok=True)
            handle = runtime.current()
            if handle is not None:
                handle.reconfigure(
                    approved_output_root=root,
                    approved_asset_roots=asset_roots,
                    execution_policy=policy,
                    runtime_mode="connector",
                )
        except Exception as exc:
            self.report({"ERROR"}, f"执行设置未应用：{exc}")
            return {"CANCELLED"}
        scene = context.scene
        scene.partme_blender_output_root = self.output_root
        scene.partme_blender_asset_root = self.asset_root
        scene.partme_blender_execution_mode = self.execution_mode
        scene.partme_blender_asset_strategy = self.asset_strategy
        self.report({"INFO"}, "执行设置已保存并应用" if handle is not None else "执行设置已保存")
        return {"FINISHED"}


class PARTMEBLENDER_OT_remote_settings(bpy.types.Operator):
    bl_idname = "partme_blender.remote_settings"
    bl_label = "远程设置"

    def execute(self, _context):
        _open_addon_preferences(__package__)
        return {"FINISHED"}


def _running_remote_transports(preferences):
    from .remote import manager
    return [
        label for transport, label in (("streamable-http", "HTTP"), ("sse", "SSE"))
        if manager().snapshot(preferences, transport)["running"]
    ]


class PARTMEBLENDER_OT_configure_remote_token(bpy.types.Operator):
    bl_idname = "partme_blender.configure_remote_token"
    bl_label = "配置远程访问 Token"
    bl_description = "设置 HTTP/SSE 客户端使用的 Bearer Token；Token 不会写入 URL、场景或回执"

    remote_token: bpy.props.StringProperty(
        name="Bearer Token",
        subtype="PASSWORD",
        description="HTTP/SSE 客户端通过 Authorization: Bearer <token> 发送此凭证",
    )

    def invoke(self, context, _event):
        preferences = _addon_preferences(context)
        if preferences is None:
            self.report({"ERROR"}, "无法读取 Add-on 设置")
            return {"CANCELLED"}
        self.remote_token = preferences.remote_token
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "remote_token", text="Bearer Token")
        layout.label(text="客户端使用 Authorization: Bearer <token>", icon="LOCKED")
        layout.label(text="不会拼入地址，也不会写入场景或回执", icon="INFO")

    def execute(self, context):
        preferences = _addon_preferences(context)
        if preferences is None:
            self.report({"ERROR"}, "无法读取 Add-on 设置")
            return {"CANCELLED"}
        running = _running_remote_transports(preferences)
        if running and self.remote_token != preferences.remote_token:
            self.report({"ERROR"}, f"请先关闭 {'、'.join(running)}，再修改 Token")
            return {"CANCELLED"}
        preferences.remote_token = self.remote_token.strip()
        self.report({"INFO"}, "远程访问 Token 已保存" if preferences.remote_token else "远程访问 Token 已清除")
        return {"FINISHED"}


class PARTMEBLENDER_OT_copy_remote_token(bpy.types.Operator):
    bl_idname = "partme_blender.copy_remote_token"
    bl_label = "复制 Token"
    bl_description = "复制当前 Bearer Token 到剪贴板，不更换凭证或中断连接；请勿分享剪贴板内容"

    @classmethod
    def poll(cls, context):
        preferences = _addon_preferences(context)
        return preferences is not None and bool(preferences.remote_token)

    def execute(self, context):
        preferences = _addon_preferences(context)
        if preferences is None or not preferences.remote_token:
            self.report({"WARNING"}, "请先配置或生成 Token")
            return {"CANCELLED"}
        context.window_manager.clipboard = preferences.remote_token
        self.report({"INFO"}, "Token 已复制到剪贴板，请妥善保管")
        return {"FINISHED"}


class PARTMEBLENDER_OT_generate_remote_token(bpy.types.Operator):
    bl_idname = "partme_blender.generate_remote_token"
    bl_label = "生成新 Token"
    bl_description = "生成强随机 Bearer Token 并复制到剪贴板；轮换前须关闭 HTTP/SSE"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        preferences = _addon_preferences(context)
        if preferences is None:
            self.report({"ERROR"}, "无法读取 Add-on 设置")
            return {"CANCELLED"}
        running = _running_remote_transports(preferences)
        if running:
            self.report({"ERROR"}, f"请先关闭 {'、'.join(running)}，再轮换 Token")
            return {"CANCELLED"}
        token = secrets.token_urlsafe(32)
        preferences.remote_token = token
        context.window_manager.clipboard = token
        self.report({"INFO"}, "新 Token 已保存并复制；请立即粘贴到客户端配置")
        return {"FINISHED"}


class PARTMEBLENDER_OT_switch_tab(bpy.types.Operator):
    bl_idname = "partme_blender.switch_tab"
    bl_label = "查看状态"
    tab: bpy.props.EnumProperty(items=_TABS)

    def execute(self, context):
        context.window_manager.partme_blender_ui_tab = self.tab
        return {"FINISHED"}


class PARTMEBLENDER_OT_refresh_access(bpy.types.Operator):
    bl_idname = "partme_blender.refresh_access"
    bl_label = "刷新接入状态"

    def execute(self, context):
        from .remote import manager
        preferences = _addon_preferences(context)
        if preferences is None:
            self.report({"ERROR"}, "无法读取 Add-on 设置")
            return {"CANCELLED"}
        status = manager().probe_stdio(preferences)
        manager().poll(preferences)
        self.report({"INFO" if status["state"] == "ready" else "WARNING"}, status["statusText"])
        return {"FINISHED"}


class PARTMEBLENDER_OT_toggle_remote(bpy.types.Operator):
    bl_idname = "partme_blender.toggle_remote"
    bl_label = "启动或停止远程 MCP"
    transport: bpy.props.EnumProperty(items=(
        ("streamable-http", "Streamable HTTP", ""), ("sse", "SSE", ""),
    ))
    enabled: bpy.props.BoolProperty()

    def execute(self, context):
        from .remote import manager
        preferences = _addon_preferences(context)
        if preferences is None:
            self.report({"ERROR"}, "无法读取 Add-on 设置")
            return {"CANCELLED"}
        if self.enabled and not runtime.is_running():
            self.report({"ERROR"}, "请先启动 Blender MCP 服务")
            return {"CANCELLED"}
        try:
            if self.enabled:
                manager().start(preferences, self.transport, descriptor_path=runtime.current().descriptor_path)
            else:
                manager().stop(preferences, self.transport)
        except Exception as exc:
            self.report({"ERROR"}, f"远程 MCP 操作失败：{exc}")
            return {"CANCELLED"}
        if not bpy.app.timers.is_registered(_poll_remote_listeners):
            bpy.app.timers.register(_poll_remote_listeners, first_interval=0.1)
        return {"FINISHED"}


class PARTMEBLENDER_OT_copy_remote_address(bpy.types.Operator):
    bl_idname = "partme_blender.copy_remote_address"
    bl_label = "复制地址"
    transport: bpy.props.EnumProperty(items=(
        ("streamable-http", "Streamable HTTP", ""), ("sse", "SSE", ""),
    ))

    def execute(self, context):
        from .remote import manager
        preferences = _addon_preferences(context)
        if preferences is None:
            return {"CANCELLED"}
        context.window_manager.clipboard = manager().address(preferences, self.transport)
        self.report({"INFO"}, "远程 MCP 地址已复制（不含凭证）")
        return {"FINISHED"}


class PARTMEBLENDER_OT_copy_session_id(bpy.types.Operator):
    bl_idname = "partme_blender.copy_session_id"
    bl_label = "复制会话 ID"

    def execute(self, context):
        handle = runtime.current()
        if handle is None:
            self.report({"ERROR"}, "当前没有活动制作会话")
            return {"CANCELLED"}
        context.window_manager.clipboard = handle.session.session_id
        self.report({"INFO"}, "会话 ID 已复制")
        return {"FINISHED"}


_PROVIDER_ICONS = {
    "local_library": "FILE_FOLDER", "polypizza": "MESH_CUBE", "polyhaven": "WORLD",
    "sketchfab": "INTERNET", "hyper3d": "MESH_CUBE", "hunyuan3d": "MESH_ICOSPHERE",
}
def _draw_progress(layout, progress, text):
    if progress is None:
        layout.label(text=text, icon="TIME")
        return
    percentage = f"{progress:.0%}"
    if hasattr(layout, "progress"):
        layout.progress(factor=progress, type="BAR", text=percentage)
    else:
        layout.label(text=f"{text} {percentage}", icon="TIME")


def _draw_approvals(layout, handle):
    pending = handle.session.pending_authorizations()
    if not pending:
        return
    box = layout.box()
    box.label(text=f"待批准操作 {len(pending)}", icon="LOCKED")
    for entry in pending[:5]:
        box.label(text=f"{entry['command']}  {entry['requestId'][:16]}")
        row = box.row(align=True)
        row.operator(PARTMEBLENDER_OT_approve_request.bl_idname, text="批准一次", icon="CHECKMARK").request_id = entry["requestId"]
        row.operator(PARTMEBLENDER_OT_deny_request.bl_idname, text="拒绝", icon="X").request_id = entry["requestId"]


def _draw_provider_rows(layout, context, category):
    from .harness.provider_registry import get_provider_registry
    providers = [row for row in get_provider_registry().snapshot(context)["providers"] if row["category"] == category]
    providers.sort(key=lambda provider: (
        int(provider.get("metadata", {}).get("uiOrder", 1000)), provider["label"].casefold(),
    ))
    if not providers:
        layout.label(text="没有已注册的供应商", icon="INFO")
        return
    compact = _sidebar_width(context) < _COMPACT_REGION_WIDTH
    for provider in providers:
        box = layout.box()
        task = provider.get("task")
        active = task is not None and task["active"]
        row = box.row(align=True)
        row.scale_y = 1.35
        # 社区式单行：左侧勾选框，名称占主体，右侧仅状态和配置。
        toggle = row.row(align=True)
        toggle.alignment = "LEFT"
        toggle.ui_units_x = 1.2
        toggle.enabled = provider["mutable"] and not active and (
            not provider["toggleLocked"] or
            (provider["configurable"] and provider["state"] == "configuration_required")
        )
        if provider["mutable"]:
            action = toggle.operator(
                PARTMEBLENDER_OT_set_provider_enabled.bl_idname,
                text="",
                icon="CHECKBOX_HLT" if provider["enabled"] else "CHECKBOX_DEHLT",
                depress=provider["enabled"],
                emboss=False,
            )
            action.provider_id = provider["providerId"]
            action.enabled = not provider["enabled"]
        else:
            toggle.label(text="", icon="CHECKBOX_HLT")
        row.label(text=provider["label"], icon=_PROVIDER_ICONS.get(provider["providerId"], "PLUGIN"))
        actions = _small_actions(row, 2.4 if provider["configurable"] and not active else 1.2)
        actions.label(text="", icon_value=_status_icon_value(provider["state"]))
        if provider["configurable"] and not active:
            action = actions.operator(
                PARTMEBLENDER_OT_provider_settings.bl_idname,
                text="", icon="PREFERENCES", emboss=False,
            )
            action.provider_id = provider["providerId"]
        if provider["state"] in {"configuration_required", "error", "unavailable"}:
            detail = box.column(align=True)
            detail.alert = provider["state"] == "error"
            _wrapped_label(detail, context, provider["statusText"])
        if active:
            _draw_progress(box, task.get("progress"), task.get("stage") or "处理中")
            task_row = box.row(align=True)
            _wrapped_label(task_row, context, task.get("stage") or "自动生成 · 正在处理")
            if "cancel" in provider["actions"]:
                cancel = _small_actions(box.row(align=True) if compact else task_row, 5.0)
                cancel.alert = True
                action = cancel.operator(
                    PARTMEBLENDER_OT_cancel_provider_task.bl_idname,
                    text="终止生成" if task.get("cancelSupported") else "停止等待",
                    icon="CANCEL",
                )
                action.provider_id = provider["providerId"]
                action.task_id = task["taskId"]
        elif task is not None and task["state"] in {"completed", "failed", "cancelled"}:
            info = box.row()
            info.alert = task["state"] == "failed"
            icon = "CHECKMARK" if task["state"] == "completed" else "INFO"
            _wrapped_label(info, context, task.get("message") or task.get("statusText") or "任务已结束", icon=icon)


def _draw_view_shortcuts(layout):
    """四个统一外框；上下无边框操作区共享视角，避免八块按钮。"""
    row = layout.row(align=False)
    for name, label, icon in (
        ("CAMERA", "相机", "CAMERA_DATA"), ("FRONT", "正面", "AXIS_FRONT"),
        ("SIDE", "侧面", "AXIS_SIDE"), ("TOP", "顶面", "AXIS_TOP"),
    ):
        tile = row.box().column(align=True)
        tile.scale_y = 1.3
        tile.operator("partme_blender.change_view", text="", icon=icon, emboss=False).view = name
        tile.operator("partme_blender.change_view", text=label, emboss=False).view = name


def _draw_work_tab(layout, context, handle):
    if handle is None:
        layout.label(text="启动本地服务后显示制作会话", icon="INFO")
        layout.operator(PARTMEBLENDER_OT_start.bl_idname, text="启动 MCP 服务", icon="PLAY")
        return
    from .harness.provider_registry import get_provider_registry

    status = handle.session.status()
    active_task = next((
        row.get("task") for row in get_provider_registry().snapshot(context)["providers"]
        if row.get("task", {}).get("active")
    ), None)
    phase = "生成素材" if active_task is not None else (
        "就绪" if status["stage"] == "Ready" else status["stage"]
    )
    progress = active_task.get("progress") if active_task is not None else status.get("progress")
    box = layout.box()
    row = box.row(align=True)
    row.label(text="会话 ID")
    value = row.row(align=True)
    value.label(text=status["sessionId"][:20] + ("…" if len(status["sessionId"]) > 20 else ""))
    _small_actions(value, 1.2).operator(PARTMEBLENDER_OT_copy_session_id.bl_idname, text="", icon="COPYDOWN", emboss=False)
    row = box.row(align=True)
    row.label(text="阶段")
    row.label(text=phase)
    row = box.row(align=True)
    row.label(text="等待操作")
    row.label(text=str(getattr(handle.executor, "pending_count", 0)))
    if progress is not None:
        _draw_progress(box, progress, phase)
    _draw_approvals(box, handle)
    row = box.row(align=True)
    row.scale_y = 1.35
    if status["paused"]:
        row.operator("partme_blender.resume_work", text="恢复制作", icon="PLAY")
    else:
        row.operator("partme_blender.pause_work", text="暂停 / 接管", icon="PAUSE")
    row.operator(PARTMEBLENDER_OT_revoke.bl_idname, text="撤销会话", icon="CANCEL")
    layout.separator()
    layout.label(text="⚡  快捷操作")
    _draw_view_shortcuts(layout)
    playback = layout.row(align=True)
    playback.scale_y = 1.25
    playing = bool(context.screen and context.screen.is_animation_playing)
    playback.operator("partme_blender.play_work", text="暂停动画" if playing else "播放动画",
                      icon="PAUSE" if playing else "PLAY", depress=playing)
    playback.prop(context.scene, "frame_current", text="帧")


def _draw_remote_transport(layout, preferences, transport, label, *, service_running):
    from .remote import manager
    snapshot = manager().snapshot(preferences, transport)
    box = layout.box()
    row = box.row(align=True)
    toggle_row = row.row(align=True)
    toggle_row.alignment = "LEFT"
    toggle_row.ui_units_x = 1.2
    toggle_row.enabled = ((service_running or snapshot["running"])
                          and snapshot["state"] != "configuration_required")
    toggle = toggle_row.operator(
        PARTMEBLENDER_OT_toggle_remote.bl_idname,
        text="",
        icon="CHECKBOX_HLT" if snapshot["running"] else "CHECKBOX_DEHLT",
        depress=snapshot["running"],
        emboss=False,
    )
    toggle.transport = transport
    toggle.enabled = not snapshot["running"]
    row.label(text=label, icon="NETWORK_DRIVE" if transport == "streamable-http" else "URL")
    state = box.row()
    state.alert = snapshot["state"] == "error"
    status_text = snapshot["statusText"]
    if snapshot["state"] == "running":
        status_text += f" · 客户端 {snapshot['clients']}"
    state.label(text=status_text, icon_value=_status_icon_value(snapshot["state"]))
    if snapshot["state"] == "running":
        address = box.row(align=True)
        address.label(text=snapshot["address"])
        # 为两个汉字及按钮内边距预留宽度，不再用固定 10% 裁切操作文字。
        action = _small_actions(address, units=3.0).operator(
            PARTMEBLENDER_OT_copy_remote_address.bl_idname, text="复制")
        action.transport = transport
    elif snapshot["state"] in {"error", "configuration_required"} and snapshot["message"]:
        _wrapped_label(box, bpy.context, snapshot["message"], icon="INFO")
        if snapshot["state"] == "configuration_required":
            box.operator(PARTMEBLENDER_OT_remote_settings.bl_idname, text="配置", icon="PREFERENCES")
    if snapshot.get("logPath"):
        property_name = "partme_http_diagnostics" if transport == "streamable-http" else "partme_sse_diagnostics"
        expanded = getattr(bpy.context.window_manager, property_name)
        box.prop(bpy.context.window_manager, property_name, text="诊断详情", emboss=False,
                 icon="TRIA_DOWN" if expanded else "TRIA_RIGHT")
        if expanded:
            detail = box.column()
            action = detail.operator("wm.path_open", text="打开日志目录", icon="FILE_FOLDER")
            action.filepath = str(Path(snapshot["logPath"]).parent)
            _wrapped_label(detail, bpy.context, Path(snapshot["logPath"]).name)


def _draw_access_tab(layout, context, running):
    from .remote import manager
    preferences = _addon_preferences(context)
    layout.label(text="本地 MCP", icon="CONSOLE")
    box = layout.box()
    stdio = manager().stdio_snapshot()
    ready = running and stdio["state"] == "ready"
    row = box.row(align=True)
    row.scale_y = 1.3
    row.label(text="stdio", icon="CONSOLE")
    row.label(text="已就绪" if ready else "不可用",
              icon_value=_status_icon_value("ready" if ready else "disabled"))
    if not ready:
        message = stdio["message"] or ("请先启动 Blender 服务" if not running else "点击顶部刷新状态探测 SDK")
        if "官方 MCP SDK" in message:
            box.label(text="未安装官方 MCP SDK", icon="ERROR")
            box.operator(PARTMEBLENDER_OT_remote_settings.bl_idname, text="配置 MCP Python", icon="PREFERENCES")
        else:
            _wrapped_label(box, context, message, icon="INFO")
    layout.separator()
    layout.label(text="远程 MCP", icon="NETWORK_DRIVE")
    if preferences is None:
        layout.label(text="无法读取远程配置", icon="ERROR")
        return
    _draw_remote_transport(
        layout, preferences, "streamable-http", "Streamable HTTP", service_running=running,
    )
    _draw_remote_transport(layout, preferences, "sse", "SSE（兼容）", service_running=running)
    auth = layout.box()
    row = auth.row(align=True)
    row.label(text="Bearer Token", icon="LOCKED")
    configured = bool(preferences.remote_token)
    row.label(text="已配置" if configured else "未配置",
              icon_value=_status_icon_value("ready" if configured else "configuration_required"))
    row = auth.row(align=True)
    row.operator(PARTMEBLENDER_OT_configure_remote_token.bl_idname, text="配置 Token")
    row.operator(
        PARTMEBLENDER_OT_generate_remote_token.bl_idname,
        text="重新生成" if configured else "生成 Token",
    )
    row.operator(PARTMEBLENDER_OT_copy_remote_token.bl_idname, text="复制 Token")
    auth.label(text="远程需鉴权，地址不含密钥", icon="INFO")
    auth.label(text="更换密钥前关闭 HTTP/SSE", icon="LOCKED")
    layout.operator(PARTMEBLENDER_OT_remote_settings.bl_idname, text="完整远程设置", icon="PREFERENCES")


def _attention(provider_snapshot, preferences, handle):
    if handle is not None:
        pending = handle.session.pending_authorizations()
        if pending:
            return "WORK", f"待批准操作 {len(pending)}", "LOCKED"
    providers = provider_snapshot["providers"]
    failed = next((row for row in providers if row.get("task", {}).get("state") == "failed"), None)
    if failed:
        return "MODELS", f"{failed['label']} 生成失败", "ERROR"
    completed = next((row for row in providers if row.get("task", {}).get("state") == "completed"), None)
    if completed:
        return "MODELS", f"{completed['label']} 生成完成", "CHECKMARK"
    if preferences is not None:
        from .remote import manager
        for transport, label in (("streamable-http", "HTTP"), ("sse", "SSE")):
            state = manager().snapshot(preferences, transport)
            if state["state"] == "error":
                return "ACCESS", f"{label} 接入错误", "ERROR"
    return None


class VIEW3D_PT_partme_blender_mcp(bpy.types.Panel):
    bl_label = "PartMe Blender MCP"
    bl_idname = "VIEW3D_PT_partme_blender_mcp"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PartMe MCP"

    def draw(self, context):
        from .harness.provider_registry import get_provider_registry

        layout = self.layout
        handle = runtime.current()
        running = runtime.is_running() and handle is not None
        provider_snapshot = get_provider_registry().snapshot(context)
        summary = provider_snapshot["summary"]

        box = layout.box()
        status_row = box.row()
        status_row.scale_y = 1.15
        status_row.label(text="Blender 服务已就绪" if running else "Blender 服务未就绪",
                         icon_value=_status_icon_value("ready_check" if running else "disabled"))
        box.separator(factor=0.25)
        row = box.row(align=True)
        row.scale_y = 1.0
        row.label(text=f"场景版本 {handle.session.scene_revision if running else 0}", icon="FILE")
        row.separator(factor=0.5)
        row.label(text=f"供应商可用 {summary['available']} / {summary['total']}", icon="ASSET_MANAGER")
        box.separator(factor=0.25)
        row = box.row(align=True)
        row.scale_y = 1.35
        row.operator(PARTMEBLENDER_OT_refresh_providers.bl_idname, text="刷新状态", icon="FILE_REFRESH")
        row.operator(PARTMEBLENDER_OT_execution_settings.bl_idname, text="执行设置", icon="PREFERENCES")

        attention = _attention(provider_snapshot, _addon_preferences(context), handle if running else None)
        if attention:
            target, message, icon = attention
            notice = layout.box()
            notice.alert = icon == "ERROR"
            _wrapped_label(notice, context, message, icon=icon)
            row = notice.row(align=True)
            action = _small_actions(row, 3.0).operator(PARTMEBLENDER_OT_switch_tab.bl_idname, text="查看")
            action.tab = target

        # ``prop_tabs_enum`` collapses to only the active item in a narrow N-panel
        # on Blender 5.x. Four explicit expanded enum buttons remain reachable at
        # the 240 px acceptance width while preserving native Blender styling.
        tabs = layout.row(align=True)
        tabs.scale_y = 1.25
        tabs.prop(context.window_manager, "partme_blender_ui_tab", expand=True)
        tab = context.window_manager.partme_blender_ui_tab
        if tab == "WORK":
            _draw_work_tab(layout, context, handle if running else None)
        elif tab == "ASSETS":
            layout.label(text="自动搜索，下载仅写授权目录", icon="INFO")
            _draw_provider_rows(layout, context, "asset_library")
        elif tab == "MODELS":
            _wrapped_label(layout, context, "勾选的模型参与自动生成；提交前仍需费用授权", icon="INFO")
            _draw_provider_rows(layout, context, "ai_model")
        else:
            _draw_access_tab(layout, context, running)


CLASSES = (
    PARTMEBLENDER_Preferences,
    PARTMEBLENDER_OT_start,
    PARTMEBLENDER_OT_revoke,
    PARTMEBLENDER_OT_approve_request,
    PARTMEBLENDER_OT_deny_request,
    PARTMEBLENDER_OT_refresh_providers,
    PARTMEBLENDER_OT_set_provider_enabled,
    PARTMEBLENDER_OT_hyper3d_oauth,
    PARTMEBLENDER_OT_provider_settings,
    PARTMEBLENDER_OT_cancel_provider_task,
    PARTMEBLENDER_OT_execution_settings,
    PARTMEBLENDER_OT_remote_settings,
    PARTMEBLENDER_OT_configure_remote_token,
    PARTMEBLENDER_OT_generate_remote_token,
    PARTMEBLENDER_OT_copy_remote_token,
    PARTMEBLENDER_OT_switch_tab,
    PARTMEBLENDER_OT_refresh_access,
    PARTMEBLENDER_OT_toggle_remote,
    PARTMEBLENDER_OT_copy_remote_address,
    PARTMEBLENDER_OT_copy_session_id,
    VIEW3D_PT_partme_blender_mcp,
)


def register():
    global _provider_sync_attempts
    _playback_snapshot.clear()
    _register_status_icons()
    bpy.types.Scene.partme_blender_execution_mode = bpy.props.EnumProperty(
        name="Execution Mode", default="auto_with_budget", items=_EXECUTION_MODES,
    )
    bpy.types.Scene.partme_blender_allow_proxies = bpy.props.BoolProperty(name="Design missing assets", default=False)
    bpy.types.Scene.partme_blender_asset_strategy = bpy.props.EnumProperty(
        name="Asset Strategy", default="auto_search_generate", items=_ASSET_STRATEGIES,
    )
    bpy.types.Scene.partme_blender_output_root = bpy.props.StringProperty(
        name="Approved Output Directory", subtype="DIR_PATH",
        description="Files exported by PartMe Blender MCP must stay under this directory",
    )
    bpy.types.Scene.partme_blender_asset_root = bpy.props.StringProperty(
        name="Approved Asset Directory", subtype="DIR_PATH",
        description="Image textures and imported assets must stay under this directory",
    )
    bpy.types.WindowManager.partme_blender_ui_tab = bpy.props.EnumProperty(
        name="PartMe Blender MCP Tab", items=_TABS, default="WORK",
    )
    bpy.types.WindowManager.partme_http_diagnostics = bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})
    bpy.types.WindowManager.partme_sse_diagnostics = bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    _provider_sync_attempts = 0
    if not bpy.app.timers.is_registered(_deferred_provider_sync):
        bpy.app.timers.register(_deferred_provider_sync, first_interval=0.1)
    if not bpy.app.timers.is_registered(_refresh_playback_ui):
        bpy.app.timers.register(_refresh_playback_ui, first_interval=0.1, persistent=True)


def unregister():
    from .remote import manager
    if bpy.app.timers.is_registered(_refresh_playback_ui):
        bpy.app.timers.unregister(_refresh_playback_ui)
    _playback_snapshot.clear()
    manager().shutdown()
    if bpy.app.timers.is_registered(_poll_remote_listeners):
        bpy.app.timers.unregister(_poll_remote_listeners)
    if bpy.app.timers.is_registered(_deferred_provider_sync):
        bpy.app.timers.unregister(_deferred_provider_sync)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    _unregister_status_icons()
    for owner, name in (
        (bpy.types.Scene, "partme_blender_output_root"),
        (bpy.types.Scene, "partme_blender_asset_root"),
        (bpy.types.Scene, "partme_blender_execution_mode"),
        (bpy.types.Scene, "partme_blender_allow_proxies"),
        (bpy.types.Scene, "partme_blender_asset_strategy"),
        (bpy.types.WindowManager, "partme_blender_ui_tab"),
        (bpy.types.WindowManager, "partme_http_diagnostics"),
        (bpy.types.WindowManager, "partme_sse_diagnostics"),
    ):
        if hasattr(owner, name):
            delattr(owner, name)
