"""PartMe 独立供应商配置探测，不依赖社区 Add-on。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from partme_blender_mcp.harness import provider_registry as module


class ProviderPreferencesTests(unittest.TestCase):
    def test_local_hunyuan_configuration_is_not_remote_validation(self):
        preferences = SimpleNamespace(hunyuan3d_mode='LOCAL_API', hunyuan3d_api_url='http://127.0.0.1:8080')
        context = SimpleNamespace(preferences=SimpleNamespace(addons={
            'partme_blender_mcp': SimpleNamespace(preferences=preferences)}))
        with patch.object(module.importlib, 'import_module', return_value=object()):
            status = module._partme_provider_status('hunyuan3d')(context)
        self.assertEqual(status['state'], 'ready')
        self.assertIn('未验证', status['statusText'])

    def test_asset_status_uses_partme_preferences_without_community_socket(self):
        prefs = SimpleNamespace(sketchfab_api_key='')
        context = SimpleNamespace(preferences=SimpleNamespace(addons={
            'partme_blender_mcp': SimpleNamespace(preferences=prefs)}))
        with patch.object(module.importlib, 'import_module', return_value=object()), \
             patch.object(module.socket, 'create_connection', side_effect=AssertionError('no community socket')):
            self.assertEqual(module._partme_provider_status('polyhaven')(context)['state'], 'ready')
            self.assertEqual(module._partme_provider_status('sketchfab')(context)['state'], 'configuration_required')
            prefs.sketchfab_api_key = 'fixture'
            self.assertEqual(module._partme_provider_status('sketchfab')(context)['state'], 'ready')

    def test_native_configuration_and_enabled_preferences(self):
        preferences = SimpleNamespace(hyper3d_auth_mode='API_KEY', hyper3d_api_key='',
                                      hunyuan3d_mode='OFFICIAL_API',
                                      hunyuan3d_secret_id='', hunyuan3d_secret_key='')
        context = SimpleNamespace(preferences=SimpleNamespace(addons={
            'partme_blender_mcp': SimpleNamespace(preferences=preferences)}))
        probe = module._partme_provider_status('hyper3d')
        self.assertEqual(probe(context)['state'], 'configuration_required')
        preferences.hyper3d_api_key = 'test-only-key'
        # 配置成功不伪装成尚未接通的生成执行器已就绪。
        self.assertEqual(probe(context)['state'], 'unavailable')
        registry = module.ProviderRegistry()
        registry.register(module.ProviderDefinition(provider_id='hyper3d', label='Rodin',
            category='ai_model', source='native', risks=('paid_generation',),
            enabled=False, status_probe=probe))
        registry.refresh(context)
        self.assertTrue(registry.set_enabled('hyper3d', True, context=context)['enabled'])

    def test_hyper3d_oauth_requires_verified_client_authorization(self):
        preferences = SimpleNamespace(hyper3d_auth_mode='MCP_OAUTH',
                                      hyper3d_oauth_status='NOT_AUTHORIZED')
        context = SimpleNamespace(preferences=SimpleNamespace(addons={
            'partme_blender_mcp': SimpleNamespace(preferences=preferences)}))
        probe = module._partme_provider_status('hyper3d')
        self.assertEqual(probe(context), {
            'state': 'configuration_required', 'statusText': '等待客户端 OAuth 授权'})
        preferences.hyper3d_oauth_status = 'AUTHORIZED'
        self.assertEqual(probe(context), {
            'state': 'unavailable', 'statusText': 'OAuth 已授权 · 客户端连接待验证'})
