"""Visible, provider-aware PartMe Blender MCP workbench in Blender's 3D View sidebar."""

import json
import os
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
_provider_sync_attempts = 0


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
        box.prop(self, "remote_token")
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

    def execute(self, context):
        from .harness.provider_registry import get_provider_registry
        provider = next((row for row in get_provider_registry().snapshot(context)["providers"]
                         if row["providerId"] == self.provider_id), None)
        if provider is None:
            self.report({"WARNING"}, f"未知供应商：{self.provider_id}")
            return {"CANCELLED"}
        module = __package__ if self.provider_id == "polypizza" else provider["metadata"].get("preferencesModule")
        if not module:
            self.report({"WARNING"}, f"{provider['label']} 没有可用的配置入口")
            return {"CANCELLED"}
        try:
            _open_addon_preferences(module)
        except Exception as exc:
            self.report({"WARNING"}, f"无法打开 {provider['label']} 配置：{exc}")
            return {"CANCELLED"}
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
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, _context):
        layout = self.layout
        for name in ("output_root", "asset_root", "execution_mode", "asset_strategy"):
            layout.label(text=self.bl_rna.properties[name].name)
            layout.prop(self, name, text="")

    def execute(self, context):
        if not bpy.path.abspath(self.output_root or ""):
            self.report({"ERROR"}, "输出目录不能为空")
            return {"CANCELLED"}
        scene = context.scene
        scene.partme_blender_output_root = self.output_root
        scene.partme_blender_asset_root = self.asset_root
        scene.partme_blender_execution_mode = self.execution_mode
        scene.partme_blender_asset_strategy = self.asset_strategy
        if runtime.is_running():
            self.report({"INFO"}, "设置已保存；授权目录变更将在下次启动 MCP 服务时生效")
        return {"FINISHED"}


class PARTMEBLENDER_OT_remote_settings(bpy.types.Operator):
    bl_idname = "partme_blender.remote_settings"
    bl_label = "远程设置"

    def execute(self, _context):
        _open_addon_preferences(__package__)
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


_PROVIDER_ICONS = {
    "local_library": "ASSET_MANAGER", "polypizza": "MESH_ICOSPHERE", "polyhaven": "WORLD",
    "sketchfab": "MESH_MONKEY", "hyper3d": "MESH_UVSPHERE", "hunyuan3d": "MESH_CUBE",
}
_STATE_ICONS = {
    "ready": "CHECKMARK", "busy": "TIME", "configuration_required": "ERROR",
    "disabled": "PAUSE", "unavailable": "UNLINKED", "error": "CANCEL",
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
    if not providers:
        layout.label(text="没有已注册的供应商", icon="INFO")
        return
    for provider in providers:
        box = layout.box()
        task = provider.get("task")
        row = box.row(align=True)
        row.label(text=provider["label"], icon=_PROVIDER_ICONS.get(provider["providerId"], "PLUGIN"))
        if category == "asset_library":
            status = row.row(align=True)
        else:
            status = box.row(align=True)
        status.alert = provider["state"] == "error"
        status.label(text=provider["statusText"], icon=_STATE_ICONS.get(provider["state"], "INFO"))
        action_row = row if category == "asset_library" else status
        if provider["configurable"]:
            settings = action_row.row(align=True)
            settings.enabled = task is None or not task["active"]
            action = settings.operator(PARTMEBLENDER_OT_provider_settings.bl_idname, text="配置")
            action.provider_id = provider["providerId"]
        if provider["mutable"]:
            toggle = row.row(align=True)
            toggle.enabled = not provider["toggleLocked"]
            action = toggle.operator(
                PARTMEBLENDER_OT_set_provider_enabled.bl_idname,
                text="开" if provider["enabled"] else "关",
                icon="CHECKBOX_HLT" if provider["enabled"] else "CHECKBOX_DEHLT",
                depress=provider["enabled"],
            )
            action.provider_id = provider["providerId"]
            action.enabled = not provider["enabled"]
        else:
            row.label(text="始终启用", icon="LOCKED")
        if task is not None and task["active"]:
            _draw_progress(box, task.get("progress"), task.get("stage") or "处理中")
            box.label(text=task.get("stage") or "自动生成 · 正在处理", icon="INFO")
            if "cancel" in provider["actions"]:
                action = box.operator(
                    PARTMEBLENDER_OT_cancel_provider_task.bl_idname, text="终止生成", icon="CANCEL",
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
    status = handle.session.status()
    box = layout.box()
    row = box.row(align=True)
    row.label(text="会话 ID")
    row.label(text=status["sessionId"][:20] + ("…" if len(status["sessionId"]) > 20 else ""))
    box.label(text="阶段  " + ("就绪" if status["stage"] == "Ready" else status["stage"]))
    box.label(text=f"等待操作  {getattr(handle.executor, 'pending_count', 0)}")
    _draw_progress(box, status.get("progress"), status.get("stage") or "制作中")
    _draw_approvals(layout, handle)
    row = layout.row(align=True)
    if status["paused"]:
        row.operator("partme_blender.resume_work", text="恢复制作", icon="PLAY")
    else:
        row.operator("partme_blender.pause_work", text="暂停 / 接管", icon="PAUSE")
    row.operator(PARTMEBLENDER_OT_revoke.bl_idname, text="撤销会话", icon="CANCEL")
    layout.label(text="快捷操作", icon="TOOL_SETTINGS")
    row = layout.row(align=True)
    for name, label in (("CAMERA", "相机"), ("FRONT", "正面"), ("SIDE", "侧面"), ("TOP", "顶面")):
        row.operator("partme_blender.change_view", text=label).view = name
    row = layout.row(align=True)
    row.operator("partme_blender.play_work", text="播放 / 暂停动画", icon="PLAY")
    row.prop(context.scene, "frame_current", text="帧")


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
    state.label(text=snapshot["statusText"], icon={
        "starting": "TIME", "running": "CHECKMARK", "stopping": "TIME",
        "stopped": "PAUSE", "error": "ERROR", "configuration_required": "ERROR",
    }[snapshot["state"]])
    if snapshot["state"] == "running":
        box.label(text=f"客户端 {snapshot['clients']}  ·  {snapshot['address']}")
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
    box.label(text="stdio  " + ("已就绪" if ready else "不可用"), icon="CHECKMARK" if ready else "UNLINKED")
    if not ready:
        box.label(text=stdio["message"] or ("请先启动 Blender 服务" if not running else "点击刷新探测 SDK"), icon="INFO")
    box.operator(PARTMEBLENDER_OT_refresh_access.bl_idname, text="刷新接入状态", icon="FILE_REFRESH")
    layout.separator()
    layout.label(text="远程 MCP", icon="NETWORK_DRIVE")
    if preferences is None:
        layout.label(text="无法读取远程配置", icon="ERROR")
        return
    _draw_remote_transport(
        layout, preferences, "streamable-http", "Streamable HTTP", service_running=running,
    )
    _draw_remote_transport(layout, preferences, "sse", "SSE（兼容）", service_running=running)
    layout.label(text="远程访问需鉴权与 HTTPS", icon="LOCKED")
    layout.operator(PARTMEBLENDER_OT_remote_settings.bl_idname, text="远程设置", icon="PREFERENCES")


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
        box.label(text="Blender 服务已就绪" if running else "Blender 服务未就绪",
                  icon="CHECKMARK" if running else "UNLINKED")
        row = box.row(align=True)
        row.label(text=f"场景版本 {handle.session.scene_revision if running else 0}", icon="FILE")
        row.label(text=f"供应商可用 {summary['available']} / {summary['total']}", icon="ASSET_MANAGER")
        row = box.row(align=True)
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

        if hasattr(layout, "prop_tabs_enum"):
            layout.prop_tabs_enum(context.window_manager, "partme_blender_ui_tab")
        else:
            layout.prop(context.window_manager, "partme_blender_ui_tab", expand=True)
        tab = context.window_manager.partme_blender_ui_tab
        if tab == "WORK":
            _draw_work_tab(layout, context, handle if running else None)
        elif tab == "ASSETS":
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
    PARTMEBLENDER_OT_switch_tab,
    PARTMEBLENDER_OT_refresh_access,
    PARTMEBLENDER_OT_toggle_remote,
    PARTMEBLENDER_OT_copy_remote_address,
    VIEW3D_PT_partme_blender_mcp,
)


def register():
    global _provider_sync_attempts
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
