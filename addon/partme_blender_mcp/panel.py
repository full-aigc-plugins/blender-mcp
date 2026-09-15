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
        handle = runtime.start(bpy, approved_output_root=root, approved_asset_roots=asset_roots, execution_policy=policy)
        self.report({"INFO"}, f"PartMe Blender MCP started: {handle.descriptor_path}")
        return {"FINISHED"}


class PARTMEBLENDER_OT_revoke(bpy.types.Operator):
    bl_idname = "partme_blender.revoke_connector"
    bl_label = "Revoke Access"

    def execute(self, _context):
        runtime.stop()
        self.report({"INFO"}, "PartMe Blender MCP access revoked")
        return {"FINISHED"}


class VIEW3D_PT_partme_blender_mcp(bpy.types.Panel):
    bl_label = "PartMe Blender MCP"
    bl_idname = "VIEW3D_PT_partme_blender_mcp"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PartMe MCP"

    def draw(self, _context):
        layout = self.layout
        if runtime.is_running():
            layout.label(text="Connected", icon="LINKED")
            layout.operator(PARTMEBLENDER_OT_revoke.bl_idname, icon="CANCEL")
        else:
            layout.label(text="Not connected", icon="UNLINKED")
            layout.prop(bpy.context.scene, "partme_blender_output_root", text="Output")
            layout.prop(bpy.context.scene, "partme_blender_asset_root", text="Assets")
            layout.prop(bpy.context.scene, "partme_blender_execution_mode", text="Mode")
            layout.prop(bpy.context.scene, "partme_blender_allow_proxies", text="Design missing assets")
            layout.operator(PARTMEBLENDER_OT_start.bl_idname, icon="PLAY")


CLASSES = (PARTMEBLENDER_OT_start, PARTMEBLENDER_OT_revoke, VIEW3D_PT_partme_blender_mcp)


def register():
    bpy.types.Scene.partme_blender_execution_mode = bpy.props.EnumProperty(
        name="Execution Mode", default="interactive",
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
