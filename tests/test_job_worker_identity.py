"""后台任务不得误用 Blender 预加载的旧 Add-on。"""
import ast
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


class WorkerIdentityTests(unittest.TestCase):
    def test_worker_loads_sibling_frame_worker_even_with_stale_package(self):
        stale = ModuleType("partme_blender_mcp.harness.frame_worker")
        stale.compose_video = stale.render_frame_sequence = lambda: None
        worker = Path(__file__).parents[1] / "src/partme_blender_mcp/harness/job_worker.py"
        tree = ast.parse(worker.read_text())
        declarations = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "spec_path"
                                                   for t in node.targets):
                break
            declarations.append(node)
        namespace = {"__file__": str(worker)}
        with patch.dict(sys.modules, {"bpy": ModuleType("bpy"), stale.__name__: stale}):
            exec(compile(ast.Module(body=declarations, type_ignores=[]), str(worker), "exec"), namespace)
        self.assertEqual(Path(namespace["compose_video"].__code__.co_filename).resolve(),
                         worker.with_name("frame_worker.py").resolve())
