"""复制凭证只写剪贴板，不修改凭证或输出明文。"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class CopyTokenTests(unittest.TestCase):
    def test_copy_and_missing_token(self):
        source = Path(__file__).parents[1] / 'addon/partme_blender_mcp/panel.py'
        tree = ast.parse(source.read_text(encoding="utf-8"))
        node = next((n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == 'PARTMEBLENDER_OT_copy_remote_token'), None)
        self.assertIsNotNone(node, '需要真正的复制 Token operator')
        prefs = SimpleNamespace(remote_token='test-only-secret')
        namespace = {'bpy': SimpleNamespace(types=SimpleNamespace(Operator=object)),
                     '_addon_preferences': lambda context: prefs}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
        cls = namespace[node.name]
        context = SimpleNamespace(window_manager=SimpleNamespace(clipboard='previous'))
        messages = []
        operator = cls()
        operator.report = lambda level, text: messages.append(text)
        self.assertTrue(cls.poll(context))
        self.assertEqual(operator.execute(context), {'FINISHED'})
        self.assertEqual(context.window_manager.clipboard, prefs.remote_token)
        self.assertNotIn(prefs.remote_token, '\n'.join(messages))
        prefs.remote_token = ''
        context.window_manager.clipboard = 'previous'
        self.assertFalse(cls.poll(context))
        self.assertEqual(operator.execute(context), {'CANCELLED'})
        self.assertEqual(context.window_manager.clipboard, 'previous')
