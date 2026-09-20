"""真实 Blender 的社区基础查询兼容性；不需要社区 Add-on 或网络。"""
import json
import sys
import bpy

sys.path.insert(0, sys.argv[sys.argv.index('--') + 1])
bpy.ops.preferences.addon_enable(module='partme_blender_mcp')
from partme_blender_mcp.harness.runtime import build_registry
from partme_blender_mcp.harness.version import PRODUCT_NAME, VERSION_TUPLE

assert 'blender_mcp_community' not in bpy.context.preferences.addons
registry = build_registry(bpy, runtime_mode='connector')
before_objects = set(bpy.data.objects)
before_groups = set(bpy.data.node_groups)
cases = {
    'ping': {}, 'get_addon_info': {}, 'get_scene_info': {}, 'get_world_state_snapshot': {},
    'get_object_info': {'name': 'Cube'},
    'describe_node_type': {'bl_idname': 'ShaderNodeMath'},
    'bpy_api_lookup': {'query': 'Object'},
}
results = {}
for command, params in cases.items():
    result = registry.dispatch('provider.query', {'providerId': 'base', 'action': command, 'params': params})['result']
    assert result and not result.get('error'), (command, result)
    results[command] = True
    if command == 'get_addon_info':
        assert result['name'] == PRODUCT_NAME and result['addon_version'] == list(VERSION_TUPLE)
        assert 'execute_code' not in result['capabilities']
assert set(bpy.data.objects) == before_objects
assert set(bpy.data.node_groups) == before_groups
print('NATIVE_BASE_QUERY=' + json.dumps(results))
bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
