"""真实 Blender 注册 Sketchfab 双认证 UI，不启动浏览器或网络请求。"""
import json
import os
import sys
from pathlib import Path

import bpy

config = os.environ.get("BLENDER_USER_CONFIG")
assert config and Path(config).is_dir()
sys.path.insert(0, sys.argv[sys.argv.index("--") + 1])
bpy.ops.preferences.addon_enable(module="partme_blender_mcp")

from partme_blender_mcp.harness.provider_registry import get_provider_registry

preferences = bpy.context.preferences.addons["partme_blender_mcp"].preferences
items = preferences.bl_rna.properties["sketchfab_auth_mode"].enum_items
assert [item.identifier for item in items] == ["API_TOKEN", "OAUTH"]
assert preferences.sketchfab_redirect_uri == "http://127.0.0.1:9879/oauth/sketchfab/callback"
assert hasattr(bpy.ops.partme_blender, "sketchfab_oauth")

preferences.sketchfab_auth_mode = "OAUTH"
preferences.sketchfab_access_token = ""
preferences.sketchfab_oauth_status = "NOT_AUTHORIZED"
row = next(item for item in get_provider_registry().refresh(bpy.context)["providers"]
           if item["providerId"] == "sketchfab")
assert row["state"] == "configuration_required"
preferences.sketchfab_access_token = "fixture-only"
preferences.sketchfab_oauth_status = "AUTHORIZED"
registry = get_provider_registry()
registry.refresh(bpy.context)
registry.set_enabled("sketchfab", True, context=bpy.context)
row = next(item for item in registry.refresh(bpy.context)["providers"]
           if item["providerId"] == "sketchfab")
assert row["statusText"] == "OAuth 已授权", row

print("NATIVE_SKETCHFAB_OAUTH=" + json.dumps({
    "passed": True, "modes": ["API_TOKEN", "OAUTH"],
    "callback": preferences.sketchfab_redirect_uri, "networkCalls": 0,
}))
bpy.ops.preferences.addon_disable(module="partme_blender_mcp")
