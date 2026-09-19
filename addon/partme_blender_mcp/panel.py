"""Visible Connector controls in Blender's 3D View sidebar."""

import bpy
from pathlib import Path

from . import runtime


class PARTMEBLENDER_OT_start(bpy.types.Operator):
    bl_idname = "partme_blender.start_connector"
    bl_label = "Start MCP Server"

    def execute(self, context):
        output_root = bpy.path.abspath(context.scene.partme_blender_output_root or "")
        if not output_root:
            self.report({"ERROR"}, "Choose an approved output directory first")
            return {"CANCELLED"}
        from pathlib import Path
        root = Path(output_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        asset_root = bpy.path.abspath(context.scene.partme_blender_asset_root or "")
        asset_roots = [Path(asset_root).resolve()] if asset_root else []
        try:
            from .harness.execution_policy import ExecutionPolicy
        except ImportError:
            from scripts.harness.execution_policy import ExecutionPolicy
        policy = ExecutionPolicy.from_dict({"mode": context.scene.partme_blender_execution_mode,
                                           "approvedOutputRoot": str(root),
                                           "allowDesignedProxies": context.scene.partme_blender_allow_proxies})
        try:
            handle = runtime.start(bpy, approved_output_root=root, approved_asset_roots=asset_roots, execution_policy=policy)
        except Exception as exc:
            self.report({"ERROR"}, f"PartMe Blender MCP did not start: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"PartMe Blender MCP started: {handle.descriptor_path}")
        return {"FINISHED"}


class PARTMEBLENDER_OT_revoke(bpy.types.Operator):
    bl_idname = "partme_blender.revoke_connector"
    bl_label = "Revoke Access"

    def execute(self, _context):
        runtime.stop()
        self.report({"INFO"}, "PartMe Blender MCP access revoked")
        return {"FINISHED"}


class PARTMEBLENDER_OT_approve_request(bpy.types.Operator):
    bl_idname = "partme_blender.approve_request"
    bl_label = "Approve Once"
    bl_description = "Approve this refused command once; the client may retry the same request id"
    request_id: bpy.props.StringProperty()

    def execute(self, _context):
        handle = runtime.current()
        if handle is None:
            self.report({"ERROR"}, "Start the MCP server first")
            return {"CANCELLED"}
        try:
            handle.session.approve_pending(self.request_id)
        except Exception as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Approved one retry of " + self.request_id)
        return {"FINISHED"}


class PARTMEBLENDER_OT_deny_request(bpy.types.Operator):
    bl_idname = "partme_blender.deny_request"
    bl_label = "Deny"
    bl_description = "Refuse this command; the same request id will not ask again"
    request_id: bpy.props.StringProperty()

    def execute(self, _context):
        handle = runtime.current()
        if handle is None:
            self.report({"ERROR"}, "Start the MCP server first")
            return {"CANCELLED"}
        try:
            handle.session.deny_pending(self.request_id)
        except Exception as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class PARTMEBLENDER_OT_refresh_providers(bpy.types.Operator):
    bl_idname = "partme_blender.refresh_providers"
    bl_label = "刷新供应商状态"

    def execute(self, _context):
        from .harness.provider_registry import reload_provider_registry
        try:
            registry = reload_provider_registry(Path(__file__).with_name("providers.json"))
        except Exception as exc:
            self.report({"WARNING"}, f"供应商目录无效：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已刷新 {len(registry.snapshot()['providers'])} 个供应商")
        return {"FINISHED"}


class PARTMEBLENDER_OT_provider_settings(bpy.types.Operator):
    bl_idname = "partme_blender.provider_settings"
    bl_label = "配置供应商"
    provider_id: bpy.props.StringProperty()

    def execute(self, _context):
        try:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
        except Exception as exc:
            self.report({"WARNING"}, f"无法打开 Blender 偏好设置：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"请在 Add-ons 中配置 {self.provider_id}")
        return {"FINISHED"}


def _draw_approvals(layout, handle):
    """Gated commands refused by the Harness wait here for a local decision."""
    pending = handle.session.pending_authorizations()
    box = layout.box()
    if not pending:
        box.label(text="No operation is waiting for approval", icon="CHECKMARK")
        return
    box.label(text=f"{len(pending)} operation(s) waiting for approval", icon="LOCKED")
    for entry in pending[:5]:
        column = box.column(align=True)
        column.label(text=f"{entry['command']}  {entry['requestId'][:20]}")
        if entry["summary"]:
            column.label(text=entry["summary"][:64])
        row = column.row(align=True)
        row.operator(PARTMEBLENDER_OT_approve_request.bl_idname, text="Approve once", icon="CHECKMARK").request_id = entry["requestId"]
        row.operator(PARTMEBLENDER_OT_deny_request.bl_idname, text="Deny", icon="X").request_id = entry["requestId"]


class VIEW3D_PT_partme_blender_mcp(bpy.types.Panel):
    bl_label = "PartMe Blender MCP"
    bl_idname = "VIEW3D_PT_partme_blender_mcp"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PartMe MCP"

    def draw(self, _context):
        layout = self.layout
        handle = runtime.current()
        running = runtime.is_running() and handle is not None

        # ── 功能区 1：连接状态 ─────────────────────────────
        box = layout.box()
        if running:
            box.label(text="已连接", icon="LINKED")
            box.label(text=f"场景版本 {handle.session.scene_revision}", icon="DOT")
            box.operator(PARTMEBLENDER_OT_revoke.bl_idname, icon="CANCEL", text="断开连接")
        else:
            box.label(text="未连接", icon="UNLINKED")
            box.operator(PARTMEBLENDER_OT_start.bl_idname, icon="PLAY", text="启动 MCP 连接")

        # ── 功能区 2：审批请求（连接中出现待审项才显示）────
        if running:
            _draw_approvals(layout, handle)



class VIEW3D_PT_partme_blender_permissions(bpy.types.Panel):
    bl_label = "权限与执行"
    bl_idname = "VIEW3D_PT_partme_blender_permissions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PartMe MCP"
    bl_parent_id = "VIEW3D_PT_partme_blender_mcp"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "partme_blender_output_root", text="输出目录")
        layout.prop(context.scene, "partme_blender_asset_root", text="素材目录")
        layout.prop(context.scene, "partme_blender_execution_mode", text="执行模式")
        layout.prop(context.scene, "partme_blender_allow_proxies", text="允许设计缺失素材的替身")


_PROVIDER_ICONS = {
    "local_library": "ASSET_MANAGER",
    "polypizza": "MESH_ICOSPHERE",
    "polyhaven": "WORLD",
    "sketchfab": "MESH_MONKEY",
    "hyper3d": "MESH_UVSPHERE",
    "hunyuan3d": "MESH_CUBE",
}


def _draw_provider_rows(layout, context, category):
    from .harness.provider_registry import get_provider_registry
    providers = [row for row in get_provider_registry().snapshot(context)["providers"]
                 if row["category"] == category]
    if not providers:
        layout.label(text="没有已注册的供应商", icon="INFO")
        return
    for provider in providers:
        box = layout.box()
        row = box.row(align=True)
        row.label(text=provider["label"], icon=_PROVIDER_ICONS.get(provider["providerId"], "PLUGIN"))
        state_icon = "CHECKMARK" if provider["state"] == "ready" else "ERROR" if provider["state"] == "error" else "INFO"
        row.label(text=provider["statusText"], icon=state_icon)
        if "configure" in provider["actions"] or provider["state"] == "configuration_required":
            action = row.operator(PARTMEBLENDER_OT_provider_settings.bl_idname, text="配置")
            action.provider_id = provider["providerId"]


class VIEW3D_PT_partme_blender_assets(bpy.types.Panel):
    bl_label = "资产与素材库"
    bl_idname = "VIEW3D_PT_partme_blender_assets"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PartMe MCP"
    bl_parent_id = "VIEW3D_PT_partme_blender_mcp"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.label(text="下载仅写入已授权素材目录", icon="LOCKED")
        row.operator(PARTMEBLENDER_OT_refresh_providers.bl_idname, text="", icon="FILE_REFRESH")
        _draw_provider_rows(self.layout, context, "asset_library")


class VIEW3D_PT_partme_blender_ai_models(bpy.types.Panel):
    bl_label = "AI 生成模型"
    bl_idname = "VIEW3D_PT_partme_blender_ai_models"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PartMe MCP"
    bl_parent_id = "VIEW3D_PT_partme_blender_mcp"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        self.layout.label(text="生成前确认外部服务、费用与保存目录", icon="INFO")
        _draw_provider_rows(self.layout, context, "ai_model")


CLASSES = (
    PARTMEBLENDER_OT_start,
    PARTMEBLENDER_OT_revoke,
    PARTMEBLENDER_OT_approve_request,
    PARTMEBLENDER_OT_deny_request,
    PARTMEBLENDER_OT_refresh_providers,
    PARTMEBLENDER_OT_provider_settings,
    VIEW3D_PT_partme_blender_mcp,
    VIEW3D_PT_partme_blender_permissions,
    VIEW3D_PT_partme_blender_assets,
    VIEW3D_PT_partme_blender_ai_models,
)


def register():
    bpy.types.Scene.partme_blender_execution_mode = bpy.props.EnumProperty(
        name="Execution Mode", default="auto_with_budget",
        items=[("interactive", "Interactive", "Review milestones"),
               ("auto_with_budget", "Automatic local design", "Complete the authorized local task and export new files"),
               ("review_only", "Read only", "Inspect without changing scene content or exporting")],
    )
    bpy.types.Scene.partme_blender_allow_proxies = bpy.props.BoolProperty(name="Design missing assets", default=False)
    bpy.types.Scene.partme_blender_output_root = bpy.props.StringProperty(
        name="Approved Output Directory",
        subtype="DIR_PATH",
        description="Files exported by PartMe Blender MCP must stay under this directory",
    )
    bpy.types.Scene.partme_blender_asset_root = bpy.props.StringProperty(
        name="Approved Asset Directory",
        subtype="DIR_PATH",
        description="Image textures and imported assets must stay under this directory",
    )
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    if hasattr(bpy.types.Scene, "partme_blender_output_root"):
        del bpy.types.Scene.partme_blender_output_root
    if hasattr(bpy.types.Scene, "partme_blender_asset_root"):
        del bpy.types.Scene.partme_blender_asset_root
    for name in ("partme_blender_execution_mode", "partme_blender_allow_proxies"):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
