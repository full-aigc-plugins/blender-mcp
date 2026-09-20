"""真实 Blender 注册双鉴权属性并验证供应商状态，不启动浏览器或网络请求。"""
import json
import os
import sys
from pathlib import Path

import bpy

config = os.environ.get('BLENDER_USER_CONFIG')
assert config and Path(config).is_dir()
assert Path(bpy.utils.user_resource('CONFIG')).resolve() == Path(config).resolve()
sys.path.insert(0, sys.argv[sys.argv.index('--') + 1])
bpy.ops.preferences.addon_enable(module='partme_blender_mcp')

from partme_blender_mcp.harness.provider_registry import get_provider_registry

preferences = bpy.context.preferences.addons['partme_blender_mcp'].preferences
registry = get_provider_registry()
assert preferences.hyper3d_auth_mode == 'MCP_OAUTH'
preferences.hyper3d_oauth_status = 'NOT_AUTHORIZED'
row = next(item for item in registry.refresh(bpy.context)['providers']
           if item['providerId'] == 'hyper3d')
assert row['state'] == 'configuration_required'

preferences.hyper3d_oauth_status = 'AUTHORIZED'
registry.refresh(bpy.context)
registry.set_enabled('hyper3d', True, context=bpy.context)
row = next(item for item in registry.refresh(bpy.context)['providers']
           if item['providerId'] == 'hyper3d')
assert row['state'] == 'unavailable' and row['statusText'] == 'OAuth 已授权 · 客户端连接待验证'

preferences.hyper3d_auth_mode = 'API_KEY'
preferences.hyper3d_api_key = ''
row = next(item for item in registry.refresh(bpy.context)['providers']
           if item['providerId'] == 'hyper3d')
assert row['state'] == 'configuration_required'
preferences.hyper3d_api_key = 'fixture-only'
row = next(item for item in registry.refresh(bpy.context)['providers']
           if item['providerId'] == 'hyper3d')
assert row['state'] == 'ready'
assert hasattr(bpy.ops.partme_blender, 'hyper3d_oauth')

print('NATIVE_HYPER3D_AUTH_MODES=' + json.dumps({
    'passed': True, 'modes': ['MCP_OAUTH', 'API_KEY'], 'networkCalls': 0,
}))
bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
