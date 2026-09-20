"""侧栏布局算法回归；真实控件外观仍需 Blender 验收。"""

import ast
from pathlib import Path
from types import SimpleNamespace
import unicodedata
import unittest


SOURCE = Path(__file__).parents[1] / "addon/partme_blender_mcp/panel.py"
HELPERS = {"_sidebar_width", "_small_actions", "_wrapped_label"}
namespace = {"unicodedata": unicodedata}
tree = ast.parse(SOURCE.read_text())
exec(compile(ast.Module(body=[node for node in tree.body
                             if isinstance(node, ast.FunctionDef) and node.name in HELPERS],
                        type_ignores=[]), str(SOURCE), "exec"), namespace)


class Layout:
    def __init__(self):
        self.labels = []

    def row(self, **kwargs):
        return self

    def column(self, **kwargs):
        return self

    def label(self, **kwargs):
        self.labels.append(kwargs)


class PanelLayoutTests(unittest.TestCase):
    def test_work_tab_preserves_design_in_narrow_sidebar(self):
        source = SOURCE.read_text()
        draw = ast.get_source_segment(source, next(n for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef) and n.name == '_draw_work_tab'))
        self.assertNotIn('if compact:', draw)
        self.assertNotIn('box.label(text="会话 ID")', draw)
        self.assertIn('if progress is not None:', draw)
        self.assertIn('_draw_approvals(box, handle)', draw)
        self.assertIn('_draw_view_shortcuts(layout)', draw)
        self.assertIn('playback.prop(context.scene, "frame_current"', draw)
        self.assertIn('context.screen.is_animation_playing', draw)
        self.assertIn('icon="PAUSE" if playing else "PLAY", depress=playing', draw)

    def test_view_cards_share_one_outer_box_without_inner_button_borders(self):
        source = SOURCE.read_text()
        node = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == '_draw_view_shortcuts')
        cards = []
        class Card:
            def __init__(self):
                self.actions = []
            def column(self, **kwargs):
                return self
            def operator(self, identifier, **kwargs):
                action = SimpleNamespace(identifier=identifier, options=kwargs)
                self.actions.append(action)
                return action
        class Row:
            def box(self):
                card = Card()
                cards.append(card)
                return card
        layout = SimpleNamespace(row=lambda **kwargs: Row())
        env = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), env)
        env['_draw_view_shortcuts'](layout)
        self.assertEqual(len(cards), 4)
        for card, view in zip(cards, ('CAMERA', 'FRONT', 'SIDE', 'TOP')):
            self.assertEqual(len(card.actions), 2)
            self.assertTrue(all(a.view == view for a in card.actions))
            self.assertTrue(all(a.options['emboss'] is False for a in card.actions))
            self.assertEqual(card.actions[0].options['text'], '')
            self.assertTrue(card.actions[1].options['text'])

    def test_assets_tab_has_only_one_short_notice(self):
        source = SOURCE.read_text()
        self.assertNotIn('layout.label(text="素材库", icon="ASSET_MANAGER")', source)
        self.assertIn('layout.label(text="自动搜索，下载仅写授权目录", icon="INFO")', source)
        self.assertNotIn('已启用供应商参与自动搜索，下载写入授权目录', source)

    def test_access_tab_uses_compact_single_line_controls(self):
        source = SOURCE.read_text()
        transport = ast.get_source_segment(source, next(n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == '_draw_remote_transport'))
        access = ast.get_source_segment(source, next(n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == '_draw_access_tab'))
        self.assertNotIn('split(factor=0.9, align=True)', transport)
        self.assertIn('_small_actions(address, units=3.0)', transport)
        self.assertIn('text="复制"', transport)
        self.assertNotIn('text="复制地址"', transport)
        self.assertNotIn('stdio 由本机智能体', access)
        self.assertIn('row.operator(PARTMEBLENDER_OT_copy_remote_token', access)
        self.assertNotIn('_wrapped_label(auth', access)
        self.assertIn('auth.label(text="远程需鉴权，地址不含密钥"', access)
        self.assertIn('auth.label(text="更换密钥前关闭 HTTP/SSE"', access)

    def test_provider_toggle_precedes_identity_and_uses_small_left_slot(self):
        source = ast.get_source_segment(SOURCE.read_text(), next(
            node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name == "_draw_provider_rows"))
        self.assertLess(source.index('PARTMEBLENDER_OT_set_provider_enabled.bl_idname'),
                        source.index('text=provider["label"]'))
        self.assertIn('toggle.alignment = "LEFT"', source)
        self.assertIn('toggle.ui_units_x = 1.2', source)
        self.assertIn('if provider["state"] in {"configuration_required", "error", "unavailable"}:', source)

    def context(self, width=562, scale=2):
        return SimpleNamespace(
            region=SimpleNamespace(width=width, view2d=SimpleNamespace(
                region_to_view=lambda x, y: (x, y))),
            preferences=SimpleNamespace(system=SimpleNamespace(ui_scale=scale)),
        )

    def test_retina_width_uses_logical_units(self):
        self.assertEqual(namespace["_sidebar_width"](self.context()), 265)
        self.assertEqual(namespace["_sidebar_width"](self.context(281, 1)), 265)

    def test_small_actions_do_not_expand_to_half_row(self):
        actions = namespace["_small_actions"](Layout(), 2.4)
        self.assertEqual(actions.alignment, "RIGHT")
        self.assertEqual(actions.ui_units_x, 2.4)

    def test_long_notice_wraps_without_losing_content(self):
        layout = Layout()
        message = "非本机绑定必须鉴权；Token 不会写入复制地址"
        namespace["_wrapped_label"](layout, self.context(), message, icon="INFO")
        self.assertGreater(len(layout.labels), 1)
        self.assertEqual("".join(row["text"] for row in layout.labels), message)
        self.assertEqual(layout.labels[0]["icon"], "INFO")
        self.assertTrue(all(row["icon"] == "NONE" for row in layout.labels[1:]))


if __name__ == "__main__":
    unittest.main()
