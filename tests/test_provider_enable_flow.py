"""缺少凭证的勾选动作必须引导配置，不能成为死控件。"""
import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from partme_blender_mcp.harness import provider_registry

SOURCE = Path(__file__).parents[1] / 'addon/partme_blender_mcp/panel.py'


def operator_class(name, namespace):
    node = next(n for n in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                if isinstance(n, ast.ClassDef) and n.name == name)
    node.body = [n for n in node.body if not isinstance(n, ast.AnnAssign)]
    namespace['__package__'] = 'partme_blender_mcp'
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace[name]


class ProviderEnableFlowTests(unittest.TestCase):
    def test_missing_credentials_opens_configuration_without_enabling(self):
        registry = Mock()
        registry.refresh.return_value = {'providers': [{'providerId': 'hyper3d',
            'state': 'configuration_required', 'configurable': True,
            'label': 'Rodin', 'statusText': '需要配置凭证'}]}
        show = Mock(return_value={'RUNNING_MODAL'})
        save = Mock()
        namespace = {'bpy': SimpleNamespace(types=SimpleNamespace(Operator=object),
            ops=SimpleNamespace(partme_blender=SimpleNamespace(provider_settings=show))),
            '_save_enabled_preference': save}
        cls = operator_class('PARTMEBLENDER_OT_set_provider_enabled', namespace)
        op = cls()
        op.provider_id, op.enabled, op.report = 'hyper3d', True, Mock()
        with patch.object(provider_registry, 'get_provider_registry', return_value=registry):
            self.assertEqual(op.execute(SimpleNamespace()), {'FINISHED'})
        show.assert_called_once_with('INVOKE_DEFAULT', provider_id='hyper3d', enable_after_save=True)
        registry.set_enabled.assert_not_called()
        save.assert_not_called()

    def check_save(self, state, enable_after_save):
        prefs = SimpleNamespace()
        registry = Mock()
        registry.refresh.return_value = {'providers': [{'providerId': 'hyper3d',
            'label': 'Rodin', 'state': state, 'statusText': state}]}
        save = Mock()
        namespace = {'bpy': SimpleNamespace(types=SimpleNamespace(Operator=object),
            ops=SimpleNamespace(wm=SimpleNamespace(save_userpref=Mock()))),
            '_addon_preferences': lambda context: prefs, '_save_enabled_preference': save}
        cls = operator_class('PARTMEBLENDER_OT_provider_settings', namespace)
        op = cls()
        op.provider_id, op.enable_after_save = 'hyper3d', enable_after_save
        op.api_key, op.hyper3d_mode, op.report = ' fixture ', 'MAIN_SITE', Mock()
        op.hyper3d_auth_mode, op.oauth_client = 'API_KEY', 'CODEX'
        context = SimpleNamespace()
        with patch.object(provider_registry, 'get_provider_registry', return_value=registry):
            self.assertEqual(op.execute(context), {'FINISHED'})
        if enable_after_save and state != 'configuration_required':
            registry.set_enabled.assert_called_once_with('hyper3d', True, context=context)
            save.assert_called_once_with(context, 'hyper3d', True)
        else:
            registry.set_enabled.assert_not_called()
            save.assert_not_called()
        self.assertEqual(prefs.hyper3d_api_key, 'fixture')
        self.assertEqual(prefs.hyper3d_auth_mode, 'API_KEY')

    def test_save_from_enable_action_enables_only_after_configuration(self):
        self.check_save('ready', True)

    def test_incomplete_configuration_does_not_enable(self):
        self.check_save('configuration_required', True)

    def test_gear_configuration_does_not_enable_implicitly(self):
        self.check_save('ready', False)
