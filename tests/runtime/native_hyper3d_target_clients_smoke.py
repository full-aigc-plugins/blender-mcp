"""真实 Blender 注册目标客户端与手动 OAuth 边界，不启动浏览器或网络请求。"""
import json
import os
import sys
from pathlib import Path

import bpy

config = os.environ.get("BLENDER_USER_CONFIG")
assert config and Path(config).is_dir()
sys.path.insert(0, sys.argv[sys.argv.index("--") + 1])
bpy.ops.preferences.addon_enable(module="partme_blender_mcp")

from partme_blender_mcp.hyper3d_auth import HYPER3D_MCP_URL, sync_preferences  # noqa: E402

preferences = bpy.context.preferences.addons["partme_blender_mcp"].preferences
items = preferences.bl_rna.properties["hyper3d_oauth_client"].enum_items
clients = [item.identifier for item in items]
assert clients == ["CODEX", "CLAUDE", "ZCODE", "KIMI", "OTHER"], clients

preferences.hyper3d_auth_mode = "MCP_OAUTH"
preferences.hyper3d_oauth_client = "ZCODE"
preferences.hyper3d_oauth_status = "AUTHORIZED"
status = sync_preferences(
    preferences,
    find=lambda _client: (_ for _ in ()).throw(AssertionError("manual target probed CLI")),
)
assert status["state"] == "manual"
assert preferences.hyper3d_oauth_status == "NOT_AUTHORIZED"

print("NATIVE_HYPER3D_TARGET_CLIENTS=" + json.dumps({
    "passed": True,
    "clients": clients,
    "manualState": status["state"],
    "url": HYPER3D_MCP_URL,
    "networkCalls": 0,
}))
bpy.ops.preferences.addon_disable(module="partme_blender_mcp")
