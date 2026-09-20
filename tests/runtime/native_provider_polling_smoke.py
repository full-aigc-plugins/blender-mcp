"""真实 Blender 中验证打包后的后台轮询；完全替身 HTTP，不写正式偏好。"""
import json
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
import bpy

config = os.environ.get('BLENDER_USER_CONFIG')
assert config and Path(config).is_dir()
assert Path(bpy.utils.user_resource('CONFIG')).resolve() == Path(config).resolve()
sys.path.insert(0, sys.argv[sys.argv.index('--') + 1])
bpy.ops.preferences.addon_enable(module='partme_blender_mcp')
from partme_blender_mcp import provider_engine as engine
from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry

tasks = get_provider_task_registry()
prefs = bpy.context.preferences.addons['partme_blender_mcp'].preferences
prefs.hyper3d_auth_mode = 'API_KEY'
prefs.hyper3d_api_key = 'fixture-only'
prefs.hyper3d_mode = 'MAIN_SITE'
entered, release = threading.Event(), threading.Event()
worker_ids = []
original_http = engine.provider_backend.requests
original_create = engine.ProviderEngine.create_rodin_job_main_site


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def json(self):
        return {'jobs': [{'status': 'Done'}]}


def post(*args, **kwargs):
    assert args[0] == 'https://api.hyper3d.com/api/v2/status'
    assert kwargs['timeout'] == (5, 20)
    assert kwargs['allow_redirects'] is False
    worker_ids.append(threading.get_ident())
    entered.set()
    assert release.wait(3), 'main thread did not release fixture request'
    return Response()


engine.provider_backend.requests = SimpleNamespace(post=post, exceptions=original_http.exceptions)
try:
    assert bpy.app.timers.is_registered(engine._redraw_provider_tasks)
    # 提交请求本身阻塞时也必须立即返回本地任务，且取消后丢弃晚到回执。
    submit_entered, submit_release = threading.Event(), threading.Event()
    submit_worker_ids = []
    def slow_submit(self, **params):
        submit_worker_ids.append(threading.get_ident())
        submit_entered.set()
        assert submit_release.wait(3), 'main thread did not release fixture submission'
        return {'subscription_key': 'late-submit'}
    engine.ProviderEngine.create_rodin_job_main_site = slow_submit
    submitted = engine.execute({'providerId': 'hyper3d', 'action': 'create_rodin_job',
                                'risk': 'paid_generation', 'params': {'text_prompt': 'fixture'}})
    submission_id = submitted['submissionId']
    assert submitted['_partmeTask']['state'] == 'submitting'
    assert submit_entered.wait(1)
    bpy.context.scene.frame_set(3)
    assert bpy.context.scene.frame_current == 3
    tasks.request_cancel('hyper3d', submission_id)
    submit_release.set()
    engine._submitter.join('hyper3d', submission_id, timeout=3)
    assert tasks.status('hyper3d', submission_id)['state'] == 'cancelled'
    assert all(value != threading.get_ident() for value in submit_worker_ids)

    for task_id, cancel in [('done-job', False), ('cancel-job', True)]:
        entered.clear()
        release.clear()
        engine.ProviderEngine.create_rodin_job_main_site = lambda self, **params: {'subscription_key': task_id}
        result = engine.execute({'providerId': 'hyper3d', 'action': 'create_rodin_job',
                                 'risk': 'paid_generation', 'params': {'text_prompt': 'fixture'}})
        local_id = result['submissionId']
        assert result['_partmeTask']['state'] == 'submitting'
        assert entered.wait(1)
        # HTTP 仍未返回时，主线程能够执行场景操作和本地取消。
        bpy.context.scene.frame_set(7 if cancel else 5)
        assert bpy.context.scene.frame_current == (7 if cancel else 5)
        if cancel:
            tasks.request_cancel('hyper3d', local_id)
        worker = engine._poller._workers[('hyper3d', local_id)]
        release.set()
        worker.join(6)
        assert not worker.is_alive()
        assert tasks.status('hyper3d', local_id)['state'] == ('cancelled' if cancel else 'completed')
        assert engine._redraw_provider_tasks() == .5
    assert all(value != threading.get_ident() for value in worker_ids)
    # 无效响应必须有界退出，不能持续把空状态当成“生成中”。
    engine._poller.interval = .01
    engine._poller.max_errors = 2
    malformed_calls = []
    class MalformedResponse(Response):
        def json(self):
            return {'jobs': []}
    def malformed_post(*args, **kwargs):
        assert args[0] == 'https://api.hyper3d.com/api/v2/status'
        malformed_calls.append(threading.get_ident())
        return MalformedResponse()
    engine.provider_backend.requests.post = malformed_post
    task_id = 'malformed-job'
    result = engine.execute({'providerId': 'hyper3d', 'action': 'create_rodin_job',
                            'risk': 'paid_generation', 'params': {'text_prompt': 'fixture'}})
    local_id = result['submissionId']
    for _ in range(100):
        worker = engine._poller._workers.get(('hyper3d', local_id))
        if worker is not None:
            break
        threading.Event().wait(.01)
    assert worker is not None
    worker.join(2)
    assert not worker.is_alive()
    assert len(malformed_calls) == 2
    assert all(value != threading.get_ident() for value in malformed_calls)
    task = tasks.status('hyper3d', local_id)
    assert task['state'] == 'failed' and '远端状态未知' in task['message']
    print('NATIVE_PROVIDER_POLLING=' + json.dumps({'passed': True,
        'backgroundQueries': len(worker_ids), 'malformedResponseQueries': len(malformed_calls),
        'backgroundSubmissions': len(submit_worker_ids),
        'mainThreadResponsive': True, 'paidNetworkCalls': 0}))
finally:
    submit_release.set()
    release.set()
    engine.ProviderEngine.create_rodin_job_main_site = original_create
    engine.provider_backend.requests = original_http
    bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
    assert not bpy.app.timers.is_registered(engine._redraw_provider_tasks)
