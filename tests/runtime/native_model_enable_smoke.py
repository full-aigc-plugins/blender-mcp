"""单 Add-on 配置/启停/执行分发；供应商 HTTP 使用替身，绝不付费提交。"""
# ruff: noqa: E402 -- Blender 必须先启用 Add-on，才能导入其运行时模块。
import json
import os
import sys
from pathlib import Path
import bpy

# 此测试会调用保存偏好的操作，必须在真实隔离的配置目录下运行。
config_root = os.environ.get('BLENDER_USER_CONFIG')
assert config_root, '必须显式设置 BLENDER_USER_CONFIG，禁止写入用户正式偏好'
assert Path(config_root).is_dir(), '隔离配置目录必须在启动 Blender 前真实存在'
assert Path(bpy.utils.user_resource('CONFIG')).resolve() == Path(config_root).resolve(), 'Blender 未使用隔离配置目录'

sys.path.insert(0, sys.argv[sys.argv.index('--') + 1])
bpy.ops.preferences.addon_enable(module='partme_blender_mcp')
assert 'blender_mcp_community' not in bpy.context.preferences.addons
from partme_blender_mcp import provider_engine
from partme_blender_mcp.harness.provider_registry import get_provider_registry
from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry
from partme_blender_mcp.harness.errors import HarnessError
prefs = bpy.context.preferences.addons['partme_blender_mcp'].preferences
registry = get_provider_registry()
for provider in ('hyper3d', 'hunyuan3d'):
    row = next(r for r in registry.refresh(bpy.context)['providers'] if r['providerId'] == provider)
    assert row['state'] == 'configuration_required', row
prefs.hyper3d_auth_mode = 'API_KEY'
prefs.hyper3d_api_key = 'fixture-not-a-real-key'
prefs.hunyuan3d_secret_id = 'fixture-id'
prefs.hunyuan3d_secret_key = 'fixture-secret'
registry.refresh(bpy.context)
for provider in ('hyper3d', 'hunyuan3d'):
    assert bpy.ops.partme_blender.set_provider_enabled(provider_id=provider, enabled=True) == {'FINISHED'}
    row = next(r for r in registry.snapshot(bpy.context)['providers'] if r['providerId'] == provider)
    assert row['enabled'] and row['state'] == 'ready', row
    assert bpy.ops.partme_blender.set_provider_enabled(provider_id=provider, enabled=False) == {'FINISHED'}
    assert not next(r for r in registry.snapshot(bpy.context)['providers'] if r['providerId'] == provider)['enabled']
calls = []
original = provider_engine.ProviderEngine.create_rodin_job_main_site
original_poll = provider_engine._start_generation_poll
provider_engine._start_generation_poll = lambda *args: None
provider_engine.ProviderEngine.create_rodin_job_main_site = lambda self, **params: calls.append(params) or {'subscription_key': 'fixture'}
try:
    result = provider_engine.execute({'providerId': 'hyper3d', 'action': 'create_rodin_job',
                                      'risk': 'paid_generation', 'params': {'text_prompt': 'fixture'}})
    assert result['_partmeTask']['state'] == 'submitting'
    local_id = result['submissionId']
    provider_engine._submitter.join('hyper3d', local_id, timeout=2)
    task = get_provider_task_registry().status('hyper3d', local_id)
    assert task['state'] == 'generating'
    assert task['remoteTaskId'] == 'fixture'
    assert next(r for r in registry.snapshot(bpy.context)['providers']
                if r['providerId'] == 'hyper3d')['task']['taskId'] == local_id
    try:
        provider_engine.execute({'providerId': 'hyper3d', 'action': 'create_rodin_job', 'risk': 'read', 'params': {}})
    except HarnessError as error:
        assert error.code == 'INVALID_ARGUMENT'
    else:
        raise AssertionError('伪造低风险请求未拒绝')
    assert len(calls) == 1
    from partme_blender_mcp.harness.runtime import build_registry
    command_registry = build_registry(bpy, runtime_mode='connector')
    get_provider_task_registry().clear()
    registry.set_enabled('hyper3d', True, context=bpy.context)
    try:
        command_registry.dispatch('provider.query', {'providerId': 'hyper3d',
            'action': 'create_rodin_job', 'params': {}})
    except HarnessError as error:
        assert error.code == 'INVALID_ARGUMENT'
    else:
        raise AssertionError('只读查询不可提交生成任务')
    assert len(calls) == 1
finally:
    provider_engine.ProviderEngine.create_rodin_job_main_site = original
    provider_engine._start_generation_poll = original_poll
assert provider_engine.ProviderEngine()._get_hyper3d_api_key() == prefs.hyper3d_api_key
assert not hasattr(bpy.types, 'BLENDERMCP_PT_Panel')
print('NATIVE_MODEL_ENABLE_SMOKE=' + json.dumps({'passed': True, 'communityEnabled': False,
      'modelCount': 2, 'paidNetworkCalls': 0}))
bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
