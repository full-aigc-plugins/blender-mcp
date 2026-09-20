"""Visible, provider-aware PartMe Blender MCP workbench in Blender's 3D View sidebar."""

import json
import os
import secrets
import shutil
import sys
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
# Blender reports region width in framebuffer pixels on Retina displays and in
# logical pixels on standard-DPI displays. 820 keeps the compact composition
# active through the documented 240 px sidebar target on both classes while a
# normally widened 320 px panel retains the one-line V4 composition.
_COMPACT_REGION_WIDTH = 820
_provider_sync_attempts = 0
_status_previews = None


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
            manager().start(preferences, transport)
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


def _apply_provider_preferences(context, *, refresh=True):
    from .harness.provider_registry import ProviderRegistryError, get_provider_registry

    _sync_polypizza_key(context)
    registry = get_provider_registry()
    stored = _enabled_preferences(context)
    for provider in registry.snapshot(context)["providers"]:
        if not provider["mutable"]:
            continue
        enabled = stored.get(provider["providerId"], provider["defaultEnabled"])
        try:
            registry.set_enabled(provider["providerId"], enabled, context=context)
        except ProviderRegistryError:
            continue
    return registry.refresh(context) if refresh else registry.snapshot(context)


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
            registry.refresh(context)
            registry.set_enabled(self.provider_id, self.enabled, context=context)
            _save_enabled_preference(context, self.provider_id, self.enabled)
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


class PARTMEBLENDER_OT_provider_settings(bpy.types.Operator):
    bl_idname = "partme_blender.provider_settings"
    bl_label = "配置供应商"
    provider_id: bpy.props.StringProperty()
    api_key: bpy.props.StringProperty(name="API Key", subtype="PASSWORD")
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

    @staticmethod
    def _community_preferences(context):
        addon = getattr(getattr(context, "preferences", None), "addons", {}).get("blender_mcp_community")
        return getattr(addon, "preferences", None)

    def invoke(self, context, _event):
        preferences = _addon_preferences(context)
        community = self._community_preferences(context)
        scene = context.scene
        if self.provider_id == "polypizza" and preferences is not None:
            self.api_key = preferences.polypizza_api_key
        elif self.provider_id == "sketchfab" and community is not None:
            self.api_key = community.sketchfab_api_key
        elif self.provider_id == "hyper3d" and community is not None:
            self.api_key = community.hyper3d_api_key
            self.hyper3d_mode = scene.blendermcp_hyper3d_mode
        elif self.provider_id == "hunyuan3d" and community is not None:
            self.hunyuan3d_mode = scene.blendermcp_hunyuan3d_mode
            self.secret_id = community.hunyuan3d_secret_id
            self.secret_key = community.hunyuan3d_secret_key
            self.api_url = community.hunyuan3d_api_url
            self.international_pro = scene.blendermcp_hunyuan3d_intl_pro
        else:
            self.report({"WARNING"}, "供应商配置不可用；请确认对应 Add-on 已启用")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(
            self, width=420, title="供应商配置", confirm_text="保存",
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
        layout.label(text="凭证仅保存在本机 Blender 用户配置中", icon="INFO")

    def execute(self, context):
        preferences = _addon_preferences(context)
        community = self._community_preferences(context)
        scene = context.scene
        if self.provider_id == "polypizza" and preferences is not None:
            preferences.polypizza_api_key = self.api_key.strip()
        elif self.provider_id == "sketchfab" and community is not None:
            community.sketchfab_api_key = self.api_key.strip()
        elif self.provider_id == "hyper3d" and community is not None:
            scene.blendermcp_hyper3d_mode = self.hyper3d_mode
            community.hyper3d_api_key = self.api_key.strip()
        elif self.provider_id == "hunyuan3d" and community is not None:
            scene.blendermcp_hunyuan3d_mode = self.hunyuan3d_mode
            community.hunyuan3d_secret_id = self.secret_id.strip()
            community.hunyuan3d_secret_key = self.secret_key.strip()
            community.hunyuan3d_api_url = self.api_url.strip()
            scene.blendermcp_hunyuan3d_intl_pro = self.international_pro
        else:
            self.report({"WARNING"}, "供应商配置不可用")
            return {"CANCELLED"}
        from .harness.provider_registry import get_provider_registry
        snapshot = get_provider_registry().refresh(context)
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


class PARTMEBLENDER_OT_generate_remote_token(bpy.types.Operator):
    bl_idname = "partme_blender.generate_remote_token"
    bl_label = "生成新 Token"
    bl_description = "生成强随机 Bearer Token 并仅在本次操作后复制到剪贴板"

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
                manager().start(preferences, self.transport)
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
    compact = getattr(context.region, "width", _COMPACT_REGION_WIDTH) < _COMPACT_REGION_WIDTH
    for provider in providers:
        box = layout.box()
        task = provider.get("task")
        active = task is not None and task["active"]
        row = box.row(align=True)
        row.scale_y = 1.35
        if category == "ai_model":
            # Keep the model identity, configuration action and enable control in
            # one restrained header. Status and task details remain on their own
            # lines so a narrow N-panel never turns the controls into two wide,
            # visually dominant buttons.
            row.label(text=provider["label"], icon=_PROVIDER_ICONS.get(provider["providerId"], "PLUGIN"))
            status = box.row(align=True)
            actions = row.row(align=True)
        elif compact and provider["configurable"]:
            identity = row.row(align=True)
            identity.label(text=provider["label"], icon=_PROVIDER_ICONS.get(provider["providerId"], "PLUGIN"))
            status = identity.row(align=True)
            actions = box.row(align=True)
        else:
            row.label(text=provider["label"], icon=_PROVIDER_ICONS.get(provider["providerId"], "PLUGIN"))
            status = row.row(align=True)
            actions = row.row(align=True)
        status.alert = provider["state"] == "error"
        status_text = provider["statusText"]
        if active and task.get("progress") is not None:
            status_text += f"  {task['progress']:.0%}"
        status.label(text=status_text, icon_value=_status_icon_value(provider["state"]))
        if provider["configurable"] and not active:
            settings = actions.row(align=True)
            compact_settings = (
                category == "ai_model" or
                (category == "asset_library" and provider["providerId"] == "polypizza")
            )
            action = settings.operator(
                PARTMEBLENDER_OT_provider_settings.bl_idname,
                text="" if compact_settings else "配置",
                icon="PREFERENCES" if compact_settings else "NONE",
                emboss=not compact_settings,
            )
            action.provider_id = provider["providerId"]
        if provider["mutable"]:
            if active:
                actions.label(text="", icon="LOCKED")
            toggle = actions.row(align=True)
            toggle.enabled = not provider["toggleLocked"]
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
            actions.label(text="始终启用", icon="LOCKED")
        if active:
            _draw_progress(box, task.get("progress"), task.get("stage") or "处理中")
            task_row = box.row(align=True)
            task_row.label(text=task.get("stage") or "自动生成 · 正在处理")
            if "cancel" in provider["actions"]:
                cancel = task_row.row(align=True)
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
            info.label(text=task.get("message") or task.get("statusText") or "任务已结束", icon=icon)


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
    compact = getattr(context.region, "width", _COMPACT_REGION_WIDTH) < _COMPACT_REGION_WIDTH
    if compact:
        box.label(text="会话 ID")
        row = box.row(align=True)
    else:
        row = box.row(align=True)
        row.label(text="会话 ID")
    value = row.box().row(align=True)
    value.label(text=status["sessionId"][:20] + ("…" if len(status["sessionId"]) > 20 else ""))
    value.operator(PARTMEBLENDER_OT_copy_session_id.bl_idname, text="", icon="COPYDOWN")
    row = box.row(align=True)
    row.label(text="阶段")
    row.box().label(text=phase)
    row = box.row(align=True)
    row.label(text="等待操作")
    row.label(text=str(getattr(handle.executor, "pending_count", 0)))
    _draw_progress(box, progress, active_task.get("stage") if active_task is not None else status.get("stage") or "制作中")
    _draw_approvals(layout, handle)
    row = layout.row(align=True)
    row.scale_y = 1.35
    if status["paused"]:
        row.operator("partme_blender.resume_work", text="恢复制作", icon="PLAY")
    else:
        row.operator("partme_blender.pause_work", text="暂停 / 接管", icon="PAUSE")
    row.operator(PARTMEBLENDER_OT_revoke.bl_idname, text="撤销会话", icon="CANCEL")
    layout.separator()
    layout.label(text="⚡  快捷操作")
    row = layout.row(align=True)
    row.scale_y = 1.5
    for name, label, icon in (
        ("CAMERA", "相机", "CAMERA_DATA"), ("FRONT", "正面", "AXIS_FRONT"),
        ("SIDE", "侧面", "AXIS_SIDE"), ("TOP", "顶面", "AXIS_TOP"),
    ):
        row.operator("partme_blender.change_view", text=label, icon=icon).view = name
    row = layout.row(align=True)
    row.scale_y = 1.25
    row.operator("partme_blender.play_work", text="播放 / 暂停动画", icon="PLAY")
    if compact:
        frame = layout.row(align=True)
        frame.prop(context.scene, "frame_current", text="当前帧")
    else:
        row.prop(context.scene, "frame_current", text="当前帧")


def _draw_remote_transport(layout, preferences, transport, label, *, service_running):
    from .remote import manager
    snapshot = manager().snapshot(preferences, transport)
    box = layout.box()
    row = box.row(align=True)
    row.label(text=label, icon="NETWORK_DRIVE" if transport == "streamable-http" else "URL")
    toggle_row = row.row(align=True)
    toggle_row.enabled = ((service_running or snapshot["running"])
                          and snapshot["state"] != "configuration_required")
    toggle = toggle_row.operator(
        PARTMEBLENDER_OT_toggle_remote.bl_idname,
        text="关" if snapshot["running"] else "开",
        icon="CHECKBOX_HLT" if snapshot["running"] else "CHECKBOX_DEHLT",
        depress=snapshot["running"],
    )
    toggle.transport = transport
    toggle.enabled = not snapshot["running"]
    state = box.row()
    state.alert = snapshot["state"] == "error"
    status_text = snapshot["statusText"]
    if snapshot["state"] == "running":
        status_text += f" · 客户端 {snapshot['clients']}"
    state.label(text=status_text, icon_value=_status_icon_value(snapshot["state"]))
    if snapshot["state"] == "running":
        box.label(text=snapshot["address"])
        action = box.operator(PARTMEBLENDER_OT_copy_remote_address.bl_idname, text="复制地址", icon="COPYDOWN")
        action.transport = transport
    elif snapshot["message"]:
        box.label(text=snapshot["message"][:120], icon="INFO")
        if snapshot["state"] == "configuration_required":
            box.operator(PARTMEBLENDER_OT_remote_settings.bl_idname, text="配置", icon="PREFERENCES")


def _draw_access_tab(layout, context, running):
    from .remote import manager
    preferences = _addon_preferences(context)
    layout.label(text="本地 MCP", icon="CONSOLE")
    layout.label(text="stdio 由本机智能体按需启动，无需开关", icon="INFO")
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
            box.label(text=message[:80], icon="INFO")
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
    row.operator(PARTMEBLENDER_OT_configure_remote_token.bl_idname, text="配置 Token", icon="PREFERENCES")
    row.operator(
        PARTMEBLENDER_OT_generate_remote_token.bl_idname,
        text="重新生成" if configured else "生成 Token",
        icon="FILE_REFRESH",
    )
    auth.label(text="非本机绑定必须鉴权；Token 不会写入复制地址", icon="INFO")
    auth.label(text="生成后仅复制一次；轮换前须关闭 HTTP/SSE", icon="LOCKED")
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
        status_row.scale_y = 1.35
        status_row.label(text="Blender 服务已就绪" if running else "Blender 服务未就绪",
                         icon_value=_status_icon_value("ready_check" if running else "disabled"))
        box.separator(factor=0.25)
        row = box.row(align=True)
        row.scale_y = 1.15
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
            row = notice.row(align=True)
            row.alert = icon == "ERROR"
            row.label(text=message, icon=icon)
            action = row.operator(PARTMEBLENDER_OT_switch_tab.bl_idname, text="查看")
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
            layout.label(text="素材库", icon="ASSET_MANAGER")
            layout.label(text="已启用供应商参与自动搜索，下载写入授权目录", icon="INFO")
            _draw_provider_rows(layout, context, "asset_library")
        elif tab == "MODELS":
            layout.label(text="已启用模型参与自动生成，任务可随时终止", icon="INFO")
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
    PARTMEBLENDER_OT_provider_settings,
    PARTMEBLENDER_OT_cancel_provider_task,
    PARTMEBLENDER_OT_execution_settings,
    PARTMEBLENDER_OT_remote_settings,
    PARTMEBLENDER_OT_configure_remote_token,
    PARTMEBLENDER_OT_generate_remote_token,
    PARTMEBLENDER_OT_switch_tab,
    PARTMEBLENDER_OT_refresh_access,
    PARTMEBLENDER_OT_toggle_remote,
    PARTMEBLENDER_OT_copy_remote_address,
    PARTMEBLENDER_OT_copy_session_id,
    VIEW3D_PT_partme_blender_mcp,
)


def register():
    global _provider_sync_attempts
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
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    _provider_sync_attempts = 0
    if not bpy.app.timers.is_registered(_deferred_provider_sync):
        bpy.app.timers.register(_deferred_provider_sync, first_interval=0.1)


def unregister():
    from .remote import manager
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
    ):
        if hasattr(owner, name):
            delattr(owner, name)
