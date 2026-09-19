"""Visible Connector controls in Blender's 3D View sidebar."""

import bpy

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

        # ── 功能区 3：授权目录 ─────────────────────────────
        box = layout.box()
        box.label(text="授权目录", icon="FILE_FOLDER")
        box.prop(bpy.context.scene, "partme_blender_output_root", text="输出目录（AI 导出仅限此处）")
        box.prop(bpy.context.scene, "partme_blender_asset_root", text="素材目录（AI 导入仅限此处）")

        # ── 功能区 4：执行模式 ─────────────────────────────
        box = layout.box()
        box.label(text="执行模式", icon="SETTINGS")
        box.prop(bpy.context.scene, "partme_blender_execution_mode", text="模式")
        box.prop(bpy.context.scene, "partme_blender_allow_proxies", text="允许设计缺失素材的替身")


CLASSES = (PARTMEBLENDER_OT_start, PARTMEBLENDER_OT_revoke, PARTMEBLENDER_OT_approve_request,
           PARTMEBLENDER_OT_deny_request, VIEW3D_PT_partme_blender_mcp)


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
