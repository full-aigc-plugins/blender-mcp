"""隔离 Blender + 本机 HTTP fixture 验证生成暂存，不触及真实供应商。"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import bpy

config = os.environ.get('BLENDER_USER_CONFIG')
assert config and Path(config).is_dir()
assert Path(bpy.utils.user_resource('CONFIG')).resolve() == Path(config).resolve()
sys.path.insert(0, sys.argv[sys.argv.index('--') + 1])
bpy.ops.preferences.addon_enable(module='partme_blender_mcp')
from partme_blender_mcp import provider_engine as engine
from partme_blender_mcp.harness.runtime import build_registry
from partme_blender_mcp.harness.provider_registry import get_provider_registry
from partme_blender_mcp.harness.session import HarnessSession
from partme_blender_mcp.harness.snapshot import BlenderCheckpointStore
from partme_blender_mcp.harness.transaction import TransactionManager
from partme_blender_mcp.harness.errors import HarnessError

with tempfile.TemporaryDirectory(prefix='partme-local-http-') as folder:
    root = Path(folder).resolve()
    fixture = root / 'fixture.glb'
    bpy.ops.export_scene.gltf(filepath=str(fixture), export_format='GLB')
    body = fixture.read_bytes()
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == '/generate'
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    try:
        prefs = bpy.context.preferences.addons['partme_blender_mcp'].preferences
        prefs.hunyuan3d_mode = 'LOCAL_API'
        prefs.hunyuan3d_api_url = f'http://127.0.0.1:{server.server_port}'
        providers = get_provider_registry()
        providers.refresh(bpy.context)
        providers.set_enabled('hunyuan3d', True, context=bpy.context)
        registry = build_registry(bpy, runtime_mode='connector', approved_asset_roots=[root])
        before = set(bpy.data.objects.keys())
        result = registry.dispatch('provider.external_action', {'providerId': 'hunyuan3d',
            'risk': 'paid_generation', 'action': 'create_hunyuan_job', 'params': {'text_prompt': 'fixture'}})
        task_id = result['result']['JobId']
        engine._local_generation._jobs[task_id]['thread'].join(5)
        state = registry.dispatch('provider.query', {'providerId': 'hunyuan3d',
            'action': 'poll_hunyuan_job_status', 'params': {'job_id': task_id}})['result']
        assert state['Status'] == 'DONE', state
        accepted = registry.dispatch('asset.fetch_generated', {'providerId': 'hunyuan3d',
            'params': {'job_id': task_id}})['result']
        assert accepted['accepted'] and accepted['operationId'], accepted
        for _ in range(100):
            staged_task = registry.dispatch('asset.operation_result', {
                'providerId': 'hunyuan3d', 'taskId': accepted['operationId']})['result']
            if not staged_task['active']:
                break
            threading.Event().wait(.01)
        assert staged_task['state'] == 'completed', staged_task
        staged = staged_task['result']
        assert Path(staged['path']).read_bytes() == body
        assert Path(staged['path']).is_relative_to(root)
        assert set(bpy.data.objects.keys()) == before, 'generation must not auto-import'
        assert len(calls) == 1
        unapproved = build_registry(bpy, runtime_mode='connector')
        try:
            unapproved.dispatch('asset.import_file', {'path': staged['path']})
        except HarnessError as error:
            assert error.code == 'ASSET_NOT_AUTHORIZED', error.code
        else:
            raise AssertionError('没有授权素材目录也能导入')
        assert set(bpy.data.objects.keys()) == before
        checkpoints = BlenderCheckpointStore(bpy, root / 'checkpoints')
        transactions = TransactionManager(capture=checkpoints.capture, restore=checkpoints.restore,
                                          journal_path=root / 'transaction-journal.json')
        session = HarnessSession('local-import', dispatch=registry.dispatch, transactions=transactions)
        def call(request_id, command, arguments, revision=0):
            return session.handle({'protocolVersion': 'codex-blender/v1', 'sessionId': 'local-import',
                'requestId': request_id, 'transactionId': 'import-generated',
                'expectedSceneRevision': revision, 'command': command, 'arguments': arguments})
        denied = call('without-transaction', 'asset.import_file', {'path': staged['path']})
        assert denied['error']['code'] == 'TRANSACTION_NOT_FOUND', denied
        assert set(bpy.data.objects.keys()) == before
        begun = call('begin-import', 'transaction.begin', {})
        assert begun['status'] == 'succeeded', begun
        stale = call('stale-import', 'asset.import_file', {'path': staged['path']}, revision=99)
        assert stale['error']['code'] == 'STALE_SCENE_REVISION', stale
        assert set(bpy.data.objects.keys()) == before
        imported = call('approved-path-import', 'asset.import_file', {'path': staged['path']})
        assert imported['status'] == 'succeeded', imported
        created = set(bpy.data.objects.keys()) - before
        assert created and set(imported['changedObjects']) == created, imported
        assert imported['sceneRevision'] == 1
        assert len(imported['result']['objects']) == len(created)
        committed = call('commit-import', 'transaction.commit', {}, revision=1)
        assert committed['status'] == 'succeeded' and committed['snapshotId'], committed
        assert transactions.status('import-generated')['state'] == 'committed'
        print('NATIVE_LOCAL_GENERATION=' + json.dumps({'passed': True, 'localHttpCalls': 1,
            'noAutomaticImport': True, 'bytes': len(body), 'paidNetworkCalls': 0,
            'transactionImport': True, 'importedObjects': len(created), 'sceneRevision': 1}))
    finally:
        server.shutdown()
        server.server_close()
        bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
