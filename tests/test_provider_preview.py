"""预览网络边界与内存返回契约，无真实密钥与网络调用。"""
import importlib.util
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from partme_blender_mcp.harness.errors import HarnessError


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.http = Mock()
        backend = SimpleNamespace(BlenderMCPServer=object, requests=self.http)
        capability_spec = importlib.util.spec_from_file_location(
            'partme_blender_mcp.hunyuan_capabilities',
            Path(__file__).parents[1] / 'addon/partme_blender_mcp/hunyuan_capabilities.py')
        capabilities = importlib.util.module_from_spec(capability_spec)
        capability_spec.loader.exec_module(capabilities)
        sdk_spec = importlib.util.spec_from_file_location(
            'partme_blender_mcp.hunyuan_sdk',
            Path(__file__).parents[1] / 'addon/partme_blender_mcp/hunyuan_sdk.py')
        sdk = importlib.util.module_from_spec(sdk_spec)
        sdk_spec.loader.exec_module(sdk)
        tokenhub_spec = importlib.util.spec_from_file_location(
            'partme_blender_mcp.tokenhub_3d',
            Path(__file__).parents[1] / 'addon/partme_blender_mcp/tokenhub_3d.py')
        tokenhub = importlib.util.module_from_spec(tokenhub_spec)
        tokenhub_spec.loader.exec_module(tokenhub)
        spec = importlib.util.spec_from_file_location('partme_blender_mcp.preview_fixture',
            Path(__file__).parents[1] / 'addon/partme_blender_mcp/provider_engine.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
                'partme_blender_mcp.provider_backend': backend,
                'partme_blender_mcp.hunyuan_capabilities': capabilities,
                'partme_blender_mcp.hunyuan_sdk': sdk,
                'partme_blender_mcp.tokenhub_3d': tokenhub,
        }):
            spec.loader.exec_module(module)
        self.module = module
        self.engine = module.ProviderEngine()
        self.engine._get_config_value = lambda *args: 'fixture-secret'

    def response(self, **values):
        response = Mock(status_code=values.pop('status_code', 200), **values)
        wrapper = Mock()
        wrapper.__enter__ = Mock(return_value=response)
        wrapper.__exit__ = Mock(return_value=False)
        return wrapper

    def prepare(self, url='https://media.sketchfab.com/model.png', body=b'\x89PNG\r\n\x1a\nfixture'):
        info = {'name': 'Chair', 'thumbnails': {'images': [{'url': url, 'width': 640, 'height': 480}]}}
        self.http.get.side_effect = [self.response(json=Mock(return_value=info)),
            self.response(iter_content=Mock(return_value=[body]))]

    def test_preview_does_not_forward_key_to_image_host(self):
        self.prepare()
        result = self.engine.get_sketchfab_model_preview('chair')
        self.assertEqual(result['format'], 'png')
        self.assertNotIn('fixture-secret', str(result))
        self.assertNotIn('headers', self.http.get.call_args_list[1].kwargs)
        self.assertFalse(self.http.get.call_args_list[1].kwargs['allow_redirects'])

    def test_sketchfab_auth_header_distinguishes_api_token_and_oauth(self):
        values = {'sketchfab_auth_mode': 'API_TOKEN', 'sketchfab_api_key': 'api-token'}
        self.engine._get_config_value = lambda _scene, name=None, _env=None: values.get(name, '')
        self.assertEqual(self.engine._sketchfab_headers(), {'Authorization': 'Token api-token'})
        values = {'sketchfab_auth_mode': 'OAUTH', 'sketchfab_access_token': 'oauth-token'}
        self.engine._get_config_value = lambda _scene, name=None, _env=None: values.get(name, '')
        self.assertEqual(self.engine._sketchfab_headers(), {'Authorization': 'Bearer oauth-token'})

    def test_untrusted_thumbnail_is_rejected_before_download(self):
        self.prepare(url='https://sketchfab.com.evil.example/model.png')
        with self.assertRaises(HarnessError):
            self.engine.get_sketchfab_model_preview('chair')
        self.assertEqual(self.http.get.call_count, 1)

    def test_oversized_and_non_image_content_are_rejected(self):
        for body in (b'x' * (5 * 1024 * 1024 + 1), b'<html>error</html>'):
            self.prepare(body=body)
            with self.assertRaises(HarnessError) as caught:
                self.engine.get_sketchfab_model_preview('chair')
            self.assertEqual(caught.exception.code, 'PROVIDER_BAD_RESULT')

    def test_invalid_uid_is_rejected_before_network(self):
        with self.assertRaises(HarnessError):
            self.engine.get_sketchfab_model_preview('../account')
        self.http.get.assert_not_called()

    def test_hunyuan_submit_rejects_unapproved_local_image_before_network(self):
        with self.assertRaises(HarnessError) as caught:
            self.engine.create_hunyuan_job_main_site(image='/private/unapproved.png')
        self.assertEqual(caught.exception.code, 'ASSET_NOT_AUTHORIZED')

    def test_tokenhub_uses_bearer_key_and_never_falls_back_to_stored_secret(self):
        values = {
            'hunyuan3d_auth_mode': 'TOKENHUB_API_KEY',
            'hunyuan3d_tokenhub_api_key': 'tokenhub-key',
            'hunyuan3d_account_region': 'MAINLAND',
            'hunyuan3d_service_type': 'AI3D',
            'hunyuan3d_task_type': 'RAPID',
        }
        self.engine._get_config_value = lambda _scene, name=None, _env=None: values.get(name, '')
        self.module.invoke_hunyuan_sdk = Mock()
        self.http.post.return_value = self.response(json=Mock(return_value={
            'id': 'job-1', 'status': 'queued'}))
        result = self.engine.create_hunyuan_job_main_site(text_prompt='chair')
        self.assertEqual(result['JobId'], 'job-1')
        self.module.invoke_hunyuan_sdk.assert_not_called()
        call = self.http.post.call_args
        self.assertEqual(call.args[0], 'https://tokenhub.tencentmaas.com/v1/api/3d/submit')
        self.assertEqual(call.kwargs['headers']['Authorization'], 'Bearer tokenhub-key')
        self.assertEqual(call.kwargs['json']['model'], 'hy-3d-express')

    def test_rodin_submission_modes_have_timeouts_and_no_redirects(self):
        self.engine._get_hyper3d_api_key = lambda: 'fixture-key'
        for method in ('create_rodin_job_main_site', 'create_rodin_job_fal_ai'):
            self.http.post.return_value = self.response(json=Mock(return_value={'request_id': '123'}))
            result = getattr(self.engine, method)(text_prompt='chair')
            self.assertEqual(result['request_id'], '123')
            self.assertEqual(self.http.post.call_args.kwargs['timeout'], (5, 30))
            self.assertFalse(self.http.post.call_args.kwargs['allow_redirects'])
        self.assertEqual(self.http.post.call_args_list[0].args[0],
                         'https://api.hyper3d.com/api/v2/rodin')

    def test_official_rodin_status_and_download_use_current_api_domain(self):
        self.engine._get_hyper3d_api_key = lambda: 'fixture-key'
        self.engine._get_config_value = lambda _scene, pref='', _env=None: (
            'MAIN_SITE' if pref == 'hyper3d_mode' else 'fixture-key')
        self.http.post.side_effect = [
            self.response(json=Mock(return_value={'jobs': [{'status': 'Done'}]})),
            self.response(status_code=201, json=Mock(return_value={'list': [{
                'name': 'model.glb', 'url': 'https://assets.hyper3d.com/result/model.glb?sig=x'}]})),
        ]
        self.assertEqual(self.engine.poll_rodin_job_status_main_site('poll-key'),
                         {'status_list': ['Done']})
        result = self.engine.resolve_rodin_asset(task_uuid='123e4567-e89b-12d3-a456-426614174000')
        self.assertEqual(result['filename'], 'model.glb')
        self.assertEqual([call.args[0] for call in self.http.post.call_args_list], [
            'https://api.hyper3d.com/api/v2/status',
            'https://api.hyper3d.com/api/v2/download',
        ])
        self.assertTrue(all(call.kwargs['allow_redirects'] is False
                            for call in self.http.post.call_args_list))

    def test_hunyuan_submit_uses_bounded_request_and_copies_profile_body(self):
        values = {
            'hunyuan3d_secret_id': 'fixture-id',
            'hunyuan3d_secret_key': 'fixture-key',
            'hunyuan3d_account_region': 'MAINLAND',
            'hunyuan3d_service_type': 'AI3D',
            'hunyuan3d_task_type': 'PROFESSIONAL',
            'hunyuan3d_intl_pro': False,
        }
        self.engine._get_config_value = lambda _scene, pref='', _env=None: values.get(pref, '')
        self.module.invoke_hunyuan_sdk = Mock(
            return_value={'Response': {'JobId': '123'}})
        result = self.engine.create_hunyuan_job_main_site(text_prompt='chair')
        self.assertEqual(result['Response']['JobId'], '123')
        sdk_call = self.module.invoke_hunyuan_sdk.call_args
        self.assertEqual(sdk_call.args[0], 'SubmitHunyuanTo3DProJob')
        self.assertEqual(sdk_call.args[1], {'Prompt': 'chair'})
        self.assertEqual(sdk_call.args[2]['version'], '2025-05-13')
        self.assertEqual(sdk_call.args[2]['region'], 'ap-guangzhou')
        self.assertEqual(sdk_call.args[2]['service'], 'ai3d')
        self.http.post.assert_not_called()

    def test_hunyuan_rapid_uses_rapid_submit_and_query_actions(self):
        values = {
            'hunyuan3d_secret_id': 'fixture-id',
            'hunyuan3d_secret_key': 'fixture-key',
            'hunyuan3d_account_region': 'MAINLAND',
            'hunyuan3d_service_type': 'AI3D',
            'hunyuan3d_task_type': 'RAPID',
            'hunyuan3d_intl_pro': False,
        }
        self.engine._get_config_value = lambda _scene, pref='', _env=None: values.get(pref, '')
        self.module.invoke_hunyuan_sdk = Mock(side_effect=[
            {'Response': {'JobId': 'rapid-1'}},
            {'Response': {'Status': 'RUN'}},
        ])
        self.engine.create_hunyuan_job_main_site(text_prompt='chair')
        self.engine.poll_hunyuan_job_status_ai(job_id='rapid-1')
        actions = [call.args[0] for call in self.module.invoke_hunyuan_sdk.call_args_list]
        self.assertEqual(actions, ['SubmitHunyuanTo3DRapidJob', 'QueryHunyuanTo3DRapidJob'])

    def test_hunyuan_invalid_profile_is_rejected_before_network(self):
        values = {
            'hunyuan3d_secret_id': 'fixture-id',
            'hunyuan3d_secret_key': 'fixture-key',
            'hunyuan3d_account_region': 'INTERNATIONAL',
            'hunyuan3d_service_type': 'HUNYUAN',
            'hunyuan3d_task_type': 'RAPID',
            'hunyuan3d_intl_pro': False,
        }
        self.engine._get_config_value = lambda _scene, pref='', _env=None: values.get(pref, '')
        with self.assertRaises(HarnessError) as caught:
            self.engine.create_hunyuan_job_main_site(text_prompt='chair')
        self.assertEqual(caught.exception.code, 'INVALID_ARGUMENT')
        self.http.post.assert_not_called()

    def test_local_hunyuan_never_enters_legacy_auto_import(self):
        prefs = SimpleNamespace(hyper3d_mode='MAIN_SITE', hunyuan3d_mode='LOCAL_API',
                                hunyuan3d_intl_pro=False)
        self.module.provider_backend.bpy = SimpleNamespace(context=SimpleNamespace(
            preferences=SimpleNamespace(addons={'partme_blender_mcp': SimpleNamespace(preferences=prefs)}),
            scene=SimpleNamespace()))
        legacy = Mock(return_value={'status': 'DONE'})
        self.module.ProviderEngine.create_hunyuan_job = legacy
        with self.assertRaises(HarnessError) as caught:
            self.module.execute({'providerId': 'hunyuan3d', 'risk': 'paid_generation',
                'action': 'create_hunyuan_job', 'params': {'text_prompt': 'fixture'}})
        self.assertEqual(caught.exception.code, 'ASSET_NOT_AUTHORIZED')
        legacy.assert_not_called()

    def test_oauth_mode_routes_generation_to_client_mcp_without_using_api_key(self):
        prefs = SimpleNamespace(hyper3d_auth_mode='MCP_OAUTH', hyper3d_api_key='must-not-use',
                                hyper3d_mode='MAIN_SITE', hunyuan3d_mode='OFFICIAL_API',
                                hunyuan3d_intl_pro=False)
        self.module.provider_backend.bpy = SimpleNamespace(context=SimpleNamespace(
            preferences=SimpleNamespace(addons={
                'partme_blender_mcp': SimpleNamespace(preferences=prefs)}),
            scene=SimpleNamespace()))
        direct = Mock(return_value={'subscription_key': 'should-not-exist'})
        self.module.ProviderEngine.create_rodin_job = direct
        with self.assertRaises(HarnessError) as caught:
            self.module.execute({'providerId': 'hyper3d', 'risk': 'paid_generation',
                'action': 'create_rodin_job', 'params': {'text_prompt': 'fixture'}})
        self.assertEqual(caught.exception.code, 'HYPER3D_CLIENT_MCP_REQUIRED')
        self.assertIn('hyper3d MCP', str(caught.exception))
        direct.assert_not_called()

    def test_automatic_poll_uses_snapshot_without_background_bpy_access(self):
        prefs = SimpleNamespace(hyper3d_api_key='fixture-key', hyper3d_mode='MAIN_SITE')
        bpy = SimpleNamespace(context=SimpleNamespace(preferences=SimpleNamespace(
            addons={'partme_blender_mcp': SimpleNamespace(preferences=prefs)})))
        self.module.provider_backend.bpy = bpy
        self.module._poller = Mock()
        self.module._start_generation_poll('create_rodin_job', {'taskId': 'job'})
        command, params, query = self.module._poller.start.call_args.args
        self.assertEqual((command, params), ('poll_rodin_job_status', {'subscription_key': 'job'}))
        bpy.context = None  # 后台回调读取 Blender 上下文就会立即失败。
        self.http.post.return_value = self.response(json=Mock(return_value={'jobs': [{'status': 'Done'}]}))
        self.assertEqual(query(), {'status_list': ['Done']})
        self.assertEqual(self.http.post.call_args.kwargs['timeout'], (5, 20))
        self.assertFalse(self.http.post.call_args.kwargs['allow_redirects'])

    def test_hunyuan_automatic_poll_uses_sdk_and_captured_capability(self):
        prefs = SimpleNamespace(
            hunyuan3d_secret_id='fixture-id', hunyuan3d_secret_key='fixture-key',
            hunyuan3d_account_region='MAINLAND', hunyuan3d_service_type='AI3D',
            hunyuan3d_task_type='RAPID', hunyuan3d_intl_pro=False,
        )
        bpy = SimpleNamespace(context=SimpleNamespace(preferences=SimpleNamespace(
            addons={'partme_blender_mcp': SimpleNamespace(preferences=prefs)})))
        self.module.provider_backend.bpy = bpy
        self.module._poller = Mock()
        self.module.invoke_hunyuan_sdk = Mock(return_value={'Response': {'Status': 'RUN'}})
        self.module._start_generation_poll('create_hunyuan_job', {
            'taskId': 'local-task', 'remoteTaskId': 'job_rapid_1'})
        command, params, query = self.module._poller.start.call_args.args
        self.assertEqual((command, params), (
            'poll_hunyuan_job_status', {'job_id': 'job_rapid_1'}))
        bpy.context = None
        self.assertEqual(query(), {'Response': {'Status': 'RUN'}})
        call = self.module.invoke_hunyuan_sdk.call_args
        self.assertEqual(call.args[0], 'QueryHunyuanTo3DRapidJob')
        self.assertEqual(call.args[1], {'JobId': 'rapid_1'})
        self.assertEqual(call.args[3:], ('fixture-id', 'fixture-key'))

    def test_asset_resolver_uses_snapshot_without_background_bpy_access(self):
        prefs = SimpleNamespace(
            hyper3d_auth_mode='API_KEY', hyper3d_api_key='fixture-key',
            hyper3d_mode='MAIN_SITE', sketchfab_api_key='',
            hunyuan3d_secret_id='', hunyuan3d_secret_key='',
            hunyuan3d_mode='OFFICIAL_API', hunyuan3d_intl_pro=False,
        )
        self.module.provider_backend.bpy = SimpleNamespace(context=SimpleNamespace(
            preferences=SimpleNamespace(addons={
                'partme_blender_mcp': SimpleNamespace(preferences=prefs)})))

        def resolve(engine, **_params):
            self.assertEqual(engine._get_hyper3d_api_key(), 'fixture-key')
            self.assertEqual(engine._get_config_value('', 'hyper3d_mode'), 'MAIN_SITE')
            return {'url': 'https://assets.hyper3d.com/model.glb', 'filename': 'model.glb'}

        self.module.ProviderEngine.resolve_rodin_asset = resolve
        callback = self.module.capture_asset_resolver(
            'hyper3d', {'task_uuid': '123e4567-e89b-12d3-a456-426614174000'})
        self.module.provider_backend.bpy.context = None
        self.assertEqual(callback(), {
            'url': 'https://assets.hyper3d.com/model.glb', 'filename': 'model.glb',
        })

    def test_official_submit_returns_before_network_and_uses_preference_snapshot(self):
        from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry
        tasks = get_provider_task_registry()
        tasks.clear()
        entered, release = threading.Event(), threading.Event()
        worker_ids = []
        prefs = SimpleNamespace(
            hyper3d_auth_mode='API_KEY', hyper3d_api_key='fixture-key',
            hyper3d_mode='MAIN_SITE', hunyuan3d_mode='OFFICIAL_API',
            hunyuan3d_secret_id='', hunyuan3d_secret_key='', hunyuan3d_intl_pro=False,
        )
        scene = SimpleNamespace(
            blendermcp_hyper3d_mode='MAIN_SITE', blendermcp_hunyuan3d_mode='OFFICIAL_API',
            blendermcp_hunyuan3d_intl_pro=False,
        )
        self.module.provider_backend.bpy = SimpleNamespace(context=SimpleNamespace(
            preferences=SimpleNamespace(addons={
                'partme_blender_mcp': SimpleNamespace(preferences=prefs)}), scene=scene))
        follow = Mock()
        self.module._start_generation_poll = follow

        def slow_submit(_engine, **_params):
            worker_ids.append(threading.get_ident())
            entered.set()
            release.wait(2)
            return {'subscription_key': 'remote-poll', 'uuid': 'remote-download'}

        self.module.ProviderEngine.create_rodin_job_main_site = slow_submit
        try:
            result = self.module.execute({
                'providerId': 'hyper3d', 'action': 'create_rodin_job',
                'risk': 'paid_generation', 'params': {'text_prompt': 'fixture'},
            })
            local_id = result['submissionId']
            self.assertEqual(result['_partmeTask']['state'], 'submitting')
            self.assertTrue(entered.wait(1))
            self.assertNotEqual(worker_ids, [threading.get_ident()])
            self.module.provider_backend.bpy.context = None
            release.set()
            self.module._submitter.join('hyper3d', local_id, timeout=2)
            task = tasks.status('hyper3d', local_id)
            self.assertEqual(task['remoteTaskId'], 'remote-poll')
            self.assertEqual(task['resultReference']['uuid'], 'remote-download')
            follow.assert_called_once()
        finally:
            release.set()
            if self.module._submitter is not None:
                self.module._submitter.close()
            tasks.clear()

    def test_asset_query_returns_before_network_and_result_is_polled(self):
        from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry
        tasks = get_provider_task_registry()
        tasks.clear()
        entered, release = threading.Event(), threading.Event()
        worker_ids = []
        prefs = SimpleNamespace(
            hyper3d_auth_mode='API_KEY', hyper3d_api_key='', hyper3d_mode='MAIN_SITE',
            hunyuan3d_mode='OFFICIAL_API', hunyuan3d_secret_id='',
            hunyuan3d_secret_key='', hunyuan3d_intl_pro=False, sketchfab_api_key='',
        )
        scene = SimpleNamespace(
            blendermcp_hyper3d_mode='MAIN_SITE', blendermcp_hunyuan3d_mode='OFFICIAL_API',
            blendermcp_hunyuan3d_intl_pro=False,
        )
        self.module.provider_backend.bpy = SimpleNamespace(context=SimpleNamespace(
            preferences=SimpleNamespace(addons={
                'partme_blender_mcp': SimpleNamespace(preferences=prefs)}), scene=scene))

        def slow_query(_engine, **_params):
            worker_ids.append(threading.get_ident())
            entered.set()
            release.wait(2)
            return {'assets': {'chair': {'name': 'Chair'}}}

        self.module.ProviderEngine.search_polyhaven_assets = slow_query
        try:
            accepted = self.module.execute({
                'providerId': 'polyhaven', 'action': 'search_polyhaven_assets',
                'risk': 'read', 'params': {'asset_type': 'models'},
            })
            query_id = accepted['queryId']
            self.assertTrue(accepted['accepted'])
            self.assertEqual(accepted['_partmeTask']['state'], 'querying')
            self.assertTrue(entered.wait(1))
            self.assertNotEqual(worker_ids, [threading.get_ident()])
            self.module.provider_backend.bpy.context = None
            release.set()
            self.module._query_runner.join('polyhaven', query_id, timeout=2)
            result = self.module.query_result('polyhaven', query_id)
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(result['result']['assets']['chair']['name'], 'Chair')
        finally:
            release.set()
            if self.module._query_runner is not None:
                self.module._query_runner.close()
                self.module._query_runner = None
            tasks.clear()

    def test_hunyuan_result_prefers_glb_and_keeps_signed_url_internal(self):
        values = {
            'hunyuan3d_mode': 'OFFICIAL_API',
            'hunyuan3d_account_region': 'MAINLAND',
            'hunyuan3d_service_type': 'AI3D',
            'hunyuan3d_task_type': 'PROFESSIONAL',
            'hunyuan3d_intl_pro': False,
        }
        self.engine._get_config_value = lambda _scene, pref='', _env=None: values.get(pref, '')
        self.engine.poll_hunyuan_job_status_ai = Mock(return_value={'Response': {
            'Status': 'DONE', 'ResultFile3Ds': [
                {'Type': 'OBJ', 'Url': 'https://bucket.cos.ap-guangzhou.tencentcos.cn/model.zip?sign=fixture'},
                {'Type': 'GLB', 'Url': 'https://bucket.cos.ap-guangzhou.tencentcos.cn/model.glb?sign=fixture'},
            ]}})
        result = self.engine.resolve_hunyuan_asset(job_id='job_123')
        self.assertEqual(result['filename'], 'hunyuan-123.glb')
        self.assertTrue(result['url'].endswith('.glb?sign=fixture'))
        self.engine.poll_hunyuan_job_status_ai.assert_called_once_with(job_id='job_123', task_type=None)

    def test_hunyuan_incomplete_error_and_untrusted_result_are_rejected(self):
        values = {
            'hunyuan3d_mode': 'OFFICIAL_API',
            'hunyuan3d_account_region': 'MAINLAND',
            'hunyuan3d_service_type': 'AI3D',
            'hunyuan3d_task_type': 'PROFESSIONAL',
            'hunyuan3d_intl_pro': False,
        }
        self.engine._get_config_value = lambda _scene, pref='', _env=None: values.get(pref, '')
        for response in (
            {'Status': 'RUN'},
            {'Error': {'Message': 'secret-url'}},
            {'Status': 'DONE', 'ResultFile3Ds': [{'Type': 'GLB', 'Url': 'http://127.0.0.1/model.glb'}]},
            {'Status': 'DONE', 'ResultFile3Ds': [{'Type': 'GLB', 'Url': 'https://tencentcos.cn.evil.example/model.glb'}]},
            {'Status': 'DONE', 'ResultFile3Ds': [{'Type': 'GLB', 'Url': 'https://bucket.tencentcos.cn/model.exe'}]},
        ):
            self.engine.poll_hunyuan_job_status_ai = Mock(return_value={'Response': response})
            with self.assertRaises(HarnessError) as caught:
                self.engine.resolve_hunyuan_asset(job_id='123')
            self.assertNotIn('secret-url', str(caught.exception))

    def test_hunyuan_invalid_reference_and_local_mode_do_not_poll(self):
        self.engine.poll_hunyuan_job_status_ai = Mock()
        values = {
            'hunyuan3d_mode': 'OFFICIAL_API',
            'hunyuan3d_account_region': 'MAINLAND',
            'hunyuan3d_service_type': 'AI3D',
            'hunyuan3d_task_type': 'PROFESSIONAL',
            'hunyuan3d_intl_pro': False,
        }
        self.engine._get_config_value = lambda _scene, pref='', _env=None: values.get(pref, '')
        with self.assertRaises(HarnessError):
            self.engine.resolve_hunyuan_asset(job_id='../other')
        values['hunyuan3d_mode'] = 'LOCAL_API'
        with self.assertRaises(HarnessError):
            self.engine.resolve_hunyuan_asset(job_id='123')
        self.engine.poll_hunyuan_job_status_ai.assert_not_called()

    def test_cancelled_native_poll_and_download_do_not_reach_backend(self):
        from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry
        tasks = get_provider_task_registry()
        tasks.clear()
        try:
            tasks.update({'operation': 'start', 'providerId': 'hyper3d', 'taskId': 'cancelled-job',
                          'state': 'generating'})
            tasks.request_cancel('hyper3d', 'cancelled-job')
            for call in (
                lambda: self.module.execute({'providerId': 'hyper3d', 'action': 'poll_rodin_job_status',
                    'risk': 'read', 'params': {'subscription_key': 'cancelled-job'}}),
                lambda: self.module.resolve_asset('hyper3d', {'task_uuid': 'cancelled-job'}),
            ):
                with self.assertRaises(HarnessError) as caught:
                    call()
                self.assertEqual(caught.exception.code, 'PROVIDER_TASK_CANCELLED')
            self.http.get.assert_not_called()
        finally:
            tasks.clear()
