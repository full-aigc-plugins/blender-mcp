"""在隔离 Blender 中验证截图成功/失败恢复和目标锁定；不访问网络。"""
# ruff: noqa: E402 -- Blender 必须先启用 Add-on，才能导入其运行时模块。

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import bpy


config = os.environ.get("BLENDER_USER_CONFIG")
assert config and Path(config).is_dir()
assert Path(bpy.utils.user_resource("CONFIG")).resolve() == Path(config).resolve()
output_root = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
output_root.mkdir(parents=True, exist_ok=True)

bpy.ops.preferences.addon_enable(module="partme_blender_mcp")
from partme_blender_mcp.harness.scene_screenshot import SceneScreenshot
from partme_blender_mcp.harness.visual_loop import VisualLoopStore


scene = bpy.context.scene
scene.frame_set(23)
original = (
    scene.camera,
    scene.frame_current,
    scene.render.filepath,
    scene.render.resolution_x,
    scene.render.resolution_y,
    scene.render.resolution_percentage,
    scene.render.image_settings.file_format,
)
screenshot = SceneScreenshot(bpy, output_root)
artifact = screenshot.capture({"path": "visual/real.png", "width": 64, "height": 48}, scene_revision=0)
restored = original == (
    scene.camera,
    scene.frame_current,
    scene.render.filepath,
    scene.render.resolution_x,
    scene.render.resolution_y,
    scene.render.resolution_percentage,
    scene.render.image_settings.file_format,
)
assert restored, "successful screenshot changed Blender state"

active_camera = scene.camera
scene.camera = None
failure_state = (
    scene.camera,
    scene.frame_current,
    scene.render.filepath,
    scene.render.resolution_x,
    scene.render.resolution_y,
    scene.render.resolution_percentage,
    scene.render.image_settings.file_format,
)
try:
    screenshot.capture({"path": "visual/missing-camera.png", "width": 32, "height": 32}, scene_revision=0)
except Exception:
    pass
else:
    raise AssertionError("render without an active camera unexpectedly succeeded")
assert failure_state == (
    scene.camera,
    scene.frame_current,
    scene.render.filepath,
    scene.render.resolution_x,
    scene.render.resolution_y,
    scene.render.resolution_percentage,
    scene.render.image_settings.file_format,
), "failed screenshot changed Blender state"
assert not (output_root / "visual/missing-camera.png").exists()
scene.camera = active_camera

target_data = Path(artifact["path"]).read_bytes()
store = VisualLoopStore(output_root)
state = store.create({
    "loopId": "native-smoke",
    "targetData": base64.b64encode(target_data).decode("ascii"),
    "minimumScore": 8,
})
assert state["target"]["sha256"] == artifact["sha256"]
assert VisualLoopStore(output_root).status({"loopId": "native-smoke"})["target"]["sha256"] == artifact["sha256"]

print("NATIVE_VISUAL_LOOP=" + json.dumps({
    "passed": True,
    "blenderVersion": bpy.app.version_string,
    "successRestored": restored,
    "failureRestored": True,
    "targetSha256": artifact["sha256"],
    "dimensions": [artifact["width"], artifact["height"]],
    "networkCalls": 0,
}))
bpy.ops.preferences.addon_disable(module="partme_blender_mcp")
