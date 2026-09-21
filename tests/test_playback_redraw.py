"""制作页播放状态刷新：仅变化时重绘，关闭窗口不保留缓存。"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


class PlaybackRedrawTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parents[1] / 'addon/partme_blender_mcp/panel.py'
        source = path.read_text(encoding="utf-8")
        node = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == '_refresh_playback_ui')
        self.calls = []
        self.area = NS(type='VIEW_3D', tag_redraw=lambda: self.calls.append(True))
        self.window = NS(as_pointer=lambda: 7, scene=NS(frame_current=33),
                         screen=NS(is_animation_playing=False, areas=[self.area]))
        self.wm = NS(partme_blender_ui_tab='WORK', windows=[self.window])
        self.env = {'bpy': NS(context=NS(window_manager=self.wm)), '_playback_snapshot': {}}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), self.env)

    def test_only_state_changes_redraw(self):
        refresh = self.env['_refresh_playback_ui']
        self.assertEqual(refresh(), 0.1)
        refresh()
        self.assertEqual(len(self.calls), 1)
        self.window.screen.is_animation_playing = True
        refresh()
        self.window.scene.frame_current = 34
        refresh()
        self.window.screen.is_animation_playing = False
        refresh()
        self.assertEqual(len(self.calls), 4)

    def test_other_tabs_and_closed_windows_clear_cache(self):
        refresh = self.env['_refresh_playback_ui']
        refresh()
        self.wm.partme_blender_ui_tab = 'ACCESS'
        refresh()
        self.assertEqual(self.env['_playback_snapshot'], {})
        self.assertEqual(len(self.calls), 1)
        self.wm.partme_blender_ui_tab = 'WORK'
        self.wm.windows = []
        refresh()
        self.assertEqual(self.env['_playback_snapshot'], {})
