"""隔离 Blender 中启用内置 Rigify 并生成真实控制骨架；禁止联网下载。"""
# ruff: noqa: E402 -- Blender 必须先启用 Add-on，才能导入其运行时模块。

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

from partme_blender_mcp.harness.runtime import build_registry


registry = build_registry(bpy, runtime_mode='connector')
before = registry.dispatch('rig.rigify_status', {})['result']
assert before['bundledAvailable'] and not before['enabled'], before
installed = registry.dispatch('rig.rigify_install', {
    'allowDownload': False, 'savePreferences': True,
})['result']
assert installed['enabled'] and installed['operatorAvailable'], installed
assert installed['mode'] == 'bundled-enable' and not installed['downloadAttempted'], installed

bpy.ops.object.armature_human_metarig_add()
metarig = bpy.context.object
metarig.name = 'PartMe Rigify MetaRig'
generated = registry.dispatch('rig.rigify_generate', {'name': metarig.name})['result']
assert generated['created'], generated
assert any(obj.type == 'ARMATURE' and obj.name != metarig.name for obj in bpy.data.objects)

print('NATIVE_RIGIFY=' + json.dumps({
    'passed': True,
    'blender': bpy.app.version_string,
    'mode': installed['mode'],
    'downloadAttempted': installed['downloadAttempted'],
    'createdObjects': len(generated['created']),
}))
bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
