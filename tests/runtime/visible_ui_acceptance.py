"""Prepare a real foreground Blender window for sidebar acceptance screenshots.

Usage:
    Blender --factory-startup --python visible_ui_acceptance.py -- ADDON_ROOT [STATE]

``STATE`` is one of ``normal``, ``generating``, ``failed``, or ``approval``.
The script only arranges real Add-on/runtime state; screenshot capture and tab
navigation remain external acceptance actions.
"""

import json
import os
import sys
import tempfile
from pathlib import Path


arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not arguments:
    raise SystemExit("pass the extracted Add-on root after '--'")
addon_root = Path(arguments[0]).resolve()
state = arguments[1] if len(arguments) > 1 else "normal"
if state not in {"normal", "generating", "failed", "approval"}:
    raise SystemExit(f"unknown UI acceptance state: {state}")
if not (addon_root / "partme_blender_mcp").is_dir():
    raise SystemExit("Add-on root must contain partme_blender_mcp/")
sys.path.insert(0, str(addon_root))

import bpy  # noqa: E402


layout_workspace = bpy.data.workspaces.get("Layout")
if layout_workspace is not None:
    bpy.context.window.workspace = layout_workspace
if (addon_root / "blender_mcp_community").is_dir():
    bpy.ops.preferences.addon_enable(module="blender_mcp_community")
bpy.ops.preferences.addon_enable(module="partme_blender_mcp")
preferences = bpy.context.preferences.addons["partme_blender_mcp"].preferences
preferences.polypizza_api_key = "visible-acceptance-key"
scene = bpy.context.scene
scene.partme_blender_output_root = tempfile.mkdtemp(prefix="partme-ui-output-")
scene.partme_blender_asset_root = tempfile.mkdtemp(prefix="partme-ui-assets-")
bpy.ops.partme_blender.start_connector()
bpy.ops.partme_blender.refresh_providers()
bpy.context.window_manager.partme_blender_ui_tab = "WORK"

from partme_blender_mcp import runtime  # noqa: E402
from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry  # noqa: E402


if state in {"generating", "failed"}:
    get_provider_task_registry().update({
        "operation": "start",
        "providerId": "hunyuan3d",
        "taskId": "visible-acceptance",
        "state": "generating",
        "progress": 0.68,
        "stage": "正在轮询生成结果",
        "cancelSupported": True,
    })
    if state == "failed":
        get_provider_task_registry().update({
            "operation": "finish",
            "providerId": "hunyuan3d",
            "taskId": "visible-acceptance",
            "state": "failed",
            "statusText": "生成失败",
            "message": "供应商返回错误，请检查密钥与预算后重试",
            "cancelSupported": True,
        })
    bpy.context.window_manager.partme_blender_ui_tab = "MODELS"
elif state == "approval":
    handle = runtime.current()
    handle.session.handle({
        "protocolVersion": "codex-blender/v1",
        "sessionId": handle.session.session_id,
        "requestId": "visible-approval",
        "transactionId": "visible-approval-transaction",
        "command": "object.delete",
        "arguments": {"name": "Cube"},
        "expectedSceneRevision": handle.session.scene_revision,
    })

view_areas = [area for area in bpy.context.screen.areas if area.type == "VIEW_3D"]
for area in view_areas:
    if area.type == "VIEW_3D":
        area.spaces.active.show_region_ui = True
if view_areas:
    largest_view = max(view_areas, key=lambda area: area.width * area.height)
    with bpy.context.temp_override(area=largest_view):
        bpy.ops.screen.screen_full_area(use_hide_panels=False)

report_path = os.environ.get("PARTME_VISIBLE_UI_REPORT")
if report_path:
    ui_widths = [
        region.width for area in bpy.context.screen.areas if area.type == "VIEW_3D"
        for region in area.regions if region.type == "UI"
    ]
    Path(report_path).write_text(json.dumps({
        "state": state,
        "activeTab": bpy.context.window_manager.partme_blender_ui_tab,
        "uiRegionWidths": ui_widths,
        "windowSize": [bpy.context.window.width, bpy.context.window.height],
    }, sort_keys=True), encoding="utf-8")

print(f"PARTME_VISIBLE_UI_READY={state}")
