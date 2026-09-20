"""真实 GLB/FBX 导出与截图路径守卫；不需要社区 Add-on。"""
import json
import sys
import tempfile
from pathlib import Path
import bpy

sys.path.insert(0, sys.argv[sys.argv.index('--') + 1])
bpy.ops.preferences.addon_enable(module='partme_blender_mcp')
from partme_blender_mcp.harness.runtime import build_registry
from partme_blender_mcp.harness.errors import HarnessError
from partme_blender_mcp.harness.session import HarnessSession

with tempfile.TemporaryDirectory(prefix='partme-compat-io-') as directory:
    root = Path(directory)
    registry = build_registry(bpy, runtime_mode='connector', approved_output_root=root)
    session = HarnessSession('compat-test', dispatch=registry.dispatch)
    before = [obj.name for obj in bpy.context.selected_objects]
    active = bpy.context.view_layer.objects.active
    for fmt in ('glb', 'fbx'):
        params = {'filepath': str(root / ('model.' + fmt)), 'format': fmt,
                  'object_names': ['Cube'], 'apply_modifiers': False}
        payload = {'protocolVersion': 'codex-blender/v1', 'sessionId': 'compat-test',
                   'requestId': fmt, 'transactionId': 'tx-' + fmt, 'expectedSceneRevision': 0,
                   'command': 'provider.external_action', 'arguments': {'providerId': 'base',
                   'action': 'export_scene', 'risk': 'external_export', 'params': params}}
        denied = session.handle(payload)
        assert denied['error']['code'] == 'AUTHORIZATION_REQUIRED', denied
        assert not Path(params['filepath']).exists()
        session.approve_pending(fmt)
        result = session.handle(payload)
        assert result['status'] == 'succeeded', result
        assert Path(params['filepath']).stat().st_size > 0
        assert [obj.name for obj in bpy.context.selected_objects] == before
        assert bpy.context.view_layer.objects.active == active
    for action in ('get_viewport_screenshot', 'export_scene'):
        try:
            registry.dispatch('provider.external_action', {'providerId': 'base', 'action': action,
                'risk': 'read' if action == 'get_viewport_screenshot' else 'external_export',
                'params': {'filepath': str(root.parent / 'partme-outside-test.png')}})
        except HarnessError as exc:
            assert exc.code == 'OUTPUT_NOT_AUTHORIZED', exc.code
        else:
            raise AssertionError('越界写入未拒绝')
    try:
        registry.dispatch('provider.query', {'providerId': 'base', 'action': 'export_scene',
            'params': {'filepath': str(root / 'bypass.glb')}})
    except HarnessError as exc:
        assert exc.code == 'INVALID_ARGUMENT', exc.code
    else:
        raise AssertionError('只读接口允许导出')
print('NATIVE_COMPAT_IO_OK: GLB, FBX, approval, path scope, selection restoration, read-risk rejection')
bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
