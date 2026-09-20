"""独立 PartMe 素材查询：Poly Haven 真实只读网络，Sketchfab 不使用真实密钥。"""
# ruff: noqa: E402 -- Blender 必须先启用 Add-on，才能导入其运行时模块。
import json
import sys
import time
import bpy

sys.path.insert(0, sys.argv[sys.argv.index('--') + 1])
bpy.ops.preferences.addon_enable(module='partme_blender_mcp')
from partme_blender_mcp.harness.provider_registry import get_provider_registry
from partme_blender_mcp.harness.runtime import build_registry

assert 'blender_mcp_community' not in bpy.context.preferences.addons
providers = get_provider_registry()
rows = {row['providerId']: row for row in providers.refresh(bpy.context)['providers']}
assert set(rows) == {'local_library', 'polyhaven', 'sketchfab', 'polypizza', 'hyper3d', 'hunyuan3d'}, rows
assert rows['polyhaven']['enabled'] and rows['polyhaven']['state'] == 'ready', rows['polyhaven']
assert rows['sketchfab']['state'] == 'configuration_required', rows['sketchfab']
commands = build_registry(bpy, runtime_mode='connector')
result = commands.dispatch('provider.query', {'providerId': 'polyhaven',
    'action': 'get_polyhaven_categories', 'params': {'asset_type': 'models'}})
accepted = result['result']
assert accepted['accepted'] and accepted['queryId'], accepted
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    result = commands.dispatch('provider.query_result', {
        'providerId': 'polyhaven', 'taskId': accepted['queryId']})['result']
    if result['state'] != 'querying':
        break
    time.sleep(.05)
assert result['state'] == 'completed', result
result = result['result']
assert result.get('categories'), result
print('NATIVE_ASSET_QUERY=' + json.dumps({'passed': True,
    'categoryCount': len(result['categories']), 'backgroundQuery': True,
    'communityAddon': False, 'paidCalls': 0}))
bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
