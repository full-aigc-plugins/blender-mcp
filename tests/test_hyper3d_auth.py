"""Hyper3D OAuth 由客户端 CLI 管理，Blender 不接触 OAuth Token。"""
import subprocess
import unittest
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
from urllib.request import url2pathname
from unittest.mock import Mock

SOURCE = Path(__file__).parents[1] / 'addon/partme_blender_mcp/hyper3d_auth.py'
SPEC = importlib.util.spec_from_file_location('partme_hyper3d_auth_test', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
HYPER3D_MCP_URL = MODULE.HYPER3D_MCP_URL
authorization_command = MODULE.authorization_command
authorization_commands = MODULE.authorization_commands
authorization_url = MODULE.authorization_url
AuthorizationRunner = MODULE.AuthorizationRunner
oauth_success_page_url = MODULE.oauth_success_page_url
inspect_client = MODULE.inspect_client
inspect_server = MODULE.inspect_server
sync_preferences = MODULE.sync_preferences


class Hyper3dAuthTests(unittest.TestCase):
    def test_codex_reuses_existing_server_and_reports_oauth(self):
        run = Mock(side_effect=[
            subprocess.CompletedProcess([], 0, stdout='hyper3d\n  url: ' + HYPER3D_MCP_URL, stderr=''),
            subprocess.CompletedProcess([], 0, stdout=json.dumps([{
                'name': 'hyper3d',
                'transport': {'type': 'streamable_http', 'url': HYPER3D_MCP_URL},
                'auth_status': 'o_auth',
            }]), stderr=''),
        ])
        self.assertTrue(inspect_server('CODEX', '/bin/codex', run=run))
        status = inspect_client('CODEX', '/bin/codex', run=run)
        self.assertEqual(status['state'], 'authorized')
        self.assertEqual(run.call_args_list[0].args[0], ['/bin/codex', 'mcp', 'get', 'hyper3d'])
        self.assertEqual(run.call_args_list[1].args[0], ['/bin/codex', 'mcp', 'list', '--json'])
        self.assertNotIn('remove', str(run.call_args_list))

    def test_other_oauth_server_cannot_authorize_hyper3d(self):
        payload = [{
            'name': 'other',
            'transport': {'type': 'streamable_http', 'url': 'https://example.com/mcp'},
            'auth_status': 'o_auth',
        }, {
            'name': 'hyper3d',
            'transport': {'type': 'streamable_http', 'url': HYPER3D_MCP_URL},
            'auth_status': 'not_logged_in',
        }]
        run = Mock(return_value=subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(payload), stderr=''))
        self.assertEqual(inspect_client('CODEX', '/bin/codex', run=run)['state'],
                         'not_authorized')

    def test_codex_add_command_is_used_only_when_missing(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 1, stdout='', stderr='not found'))
        self.assertFalse(inspect_server('CODEX', '/bin/codex', run=run))
        self.assertEqual(authorization_command('CODEX', '/bin/codex', configured=False), [
            '/bin/codex', 'mcp', 'add', 'hyper3d', '--url', HYPER3D_MCP_URL,
        ])

    def test_missing_codex_server_is_added_then_logged_in(self):
        self.assertEqual(authorization_commands('CODEX', '/bin/codex', configured=False), [
            ['/bin/codex', 'mcp', 'add', 'hyper3d', '--url', HYPER3D_MCP_URL],
            ['/bin/codex', 'mcp', 'login', 'hyper3d'],
        ])

    def test_configured_codex_server_is_reused_for_login(self):
        self.assertEqual(authorization_commands('CODEX', '/bin/codex', configured=True), [
            ['/bin/codex', 'mcp', 'login', 'hyper3d'],
        ])

    def test_claude_add_uses_user_http_scope(self):
        self.assertEqual(authorization_command('CLAUDE', '/bin/claude', configured=False), [
            '/bin/claude', 'mcp', 'add', '--transport', 'http', 'hyper3d',
            '--scope', 'user', HYPER3D_MCP_URL,
        ])

    def test_missing_claude_server_is_added_then_logged_in(self):
        self.assertEqual(authorization_commands('CLAUDE', '/bin/claude', configured=False), [
            ['/bin/claude', 'mcp', 'add', '--transport', 'http', 'hyper3d',
             '--scope', 'user', HYPER3D_MCP_URL],
            ['/bin/claude', 'mcp', 'login', 'hyper3d'],
        ])

    def test_login_commands_never_contain_credentials(self):
        self.assertEqual(authorization_command('CODEX', '/bin/codex', configured=True),
                         ['/bin/codex', 'mcp', 'login', 'hyper3d'])
        self.assertEqual(authorization_command('CLAUDE', '/bin/claude', configured=True),
                         ['/bin/claude', 'mcp', 'login', 'hyper3d'])

    def test_only_official_hyper3d_authorization_url_is_openable(self):
        official = ('https://api.hyper3d.com/api/grant/oauth/authorize?response_type=code'
                    '&state=fixture')
        self.assertEqual(authorization_url(f'Authorize by opening {official}'), official)
        self.assertIsNone(authorization_url('Documentation: https://example.com/oauth'))
        self.assertIsNone(authorization_url('https://api.hyper3d.com/api/mcp'))

    def test_authorization_runner_executes_add_then_login_and_opens_once(self):
        calls = []
        opened = []
        auth_url = 'https://api.hyper3d.com/api/grant/oauth/authorize?state=fixture'

        class Process:
            def __init__(self, lines):
                self.stdout = lines

            def wait(self):
                return 0

            def poll(self):
                return 0


        def popen(command, **kwargs):
            calls.append((command, kwargs))
            lines = [] if command[2] == 'add' else [f'Open {auth_url}\n', f'Again {auth_url}\n']
            return Process(lines)

        commands = authorization_commands('CODEX', '/bin/codex', configured=False)
        runner = AuthorizationRunner(
            commands,
            popen=popen,
            open_url=opened.append,
            success_url=lambda: 'file:///tmp/partme-oauth-success.html',
        )
        runner._run()
        self.assertEqual([item[0] for item in calls], commands)
        self.assertEqual(opened, [auth_url, 'file:///tmp/partme-oauth-success.html'])
        self.assertEqual(runner.returncode, 0)

    def test_oauth_success_page_is_centered_and_contains_no_credentials(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            url = oauth_success_page_url(directory)
            page_path = Path(url2pathname(urlparse(url).path))
            page = page_path.read_text(encoding='utf-8')

        self.assertIn('display:grid', page)
        self.assertIn('place-items:center', page)
        self.assertIn('Hyper3D MCP 授权成功', page)
        self.assertIn('可以关闭此页面并返回 Blender', page)
        self.assertNotIn('access_token', page.lower())
        self.assertNotIn('refresh_token', page.lower())

    def test_wrong_existing_url_is_rejected_not_overwritten(self):
        run = Mock(return_value=subprocess.CompletedProcess(
            [], 0, stdout='hyper3d\n  url: https://example.invalid/mcp', stderr=''))
        with self.assertRaisesRegex(ValueError, '地址不一致'):
            inspect_server('CODEX', '/bin/codex', run=run)
        self.assertEqual(run.call_count, 1)

    def test_refresh_reuses_external_codex_authorization(self):
        preferences = SimpleNamespace(
            hyper3d_auth_mode='MCP_OAUTH',
            hyper3d_oauth_client='CODEX',
            hyper3d_oauth_status='NOT_AUTHORIZED',
        )
        status = sync_preferences(
            preferences,
            find=lambda client: '/bin/codex',
            inspect=lambda client, executable: {
                'state': 'authorized', 'statusText': '客户端 OAuth 已授权'},
        )
        self.assertEqual(status['state'], 'authorized')
        self.assertEqual(preferences.hyper3d_oauth_status, 'AUTHORIZED')

    def test_api_key_mode_never_invokes_client_cli(self):
        preferences = SimpleNamespace(
            hyper3d_auth_mode='API_KEY',
            hyper3d_oauth_client='CODEX',
            hyper3d_oauth_status='AUTHORIZED',
        )
        find = Mock(side_effect=AssertionError('client lookup must not run'))
        status = sync_preferences(preferences, find=find, inspect=Mock())
        self.assertEqual(status['state'], 'not_applicable')
        find.assert_not_called()

    def test_unknown_client_state_does_not_claim_authorized(self):
        preferences = SimpleNamespace(
            hyper3d_auth_mode='MCP_OAUTH',
            hyper3d_oauth_client='CODEX',
            hyper3d_oauth_status='AUTHORIZED',
        )
        sync_preferences(
            preferences,
            find=lambda client: '/bin/codex',
            inspect=lambda client, executable: {
                'state': 'unknown', 'statusText': '授权状态待检测'},
        )
        self.assertEqual(preferences.hyper3d_oauth_status, 'ERROR')

    def test_manual_target_client_is_not_probed_as_an_automatic_cli(self):
        preferences = SimpleNamespace(
            hyper3d_auth_mode='MCP_OAUTH',
            hyper3d_oauth_client='ZCODE',
            hyper3d_oauth_status='NOT_AUTHORIZED',
        )
        find = Mock(side_effect=AssertionError('manual client must not be probed'))
        status = sync_preferences(preferences, find=find, inspect=Mock())
        self.assertEqual(status['state'], 'manual')
        self.assertEqual(preferences.hyper3d_oauth_status, 'NOT_AUTHORIZED')
        find.assert_not_called()


if __name__ == '__main__':
    unittest.main()
