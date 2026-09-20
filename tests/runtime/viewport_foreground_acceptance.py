"""在独立前台进程验证视角、聚焦、播放和审阅窗口。"""
import json
import sys
from pathlib import Path
import bpy
from scripts.harness.runtime import build_registry

output = Path(sys.argv[sys.argv.index("--") + 1])


def run():
    report = {"passed": False}
    try:
        registry = build_registry(bpy)
        for view in ("CAMERA", "FRONT", "SIDE", "TOP"):
            assert registry.dispatch("view.set", {"view": view})["result"]["view"] == view
        assert registry.dispatch("view.focus", {"object": "Cube"})["result"]["focusedObject"] == "Cube"
        assert registry.dispatch("playback.set", {"playing": True})["result"]["playing"]
        assert not registry.dispatch("playback.set", {"playing": False})["result"]["playing"]
        assert registry.dispatch("view.present", {})["result"]["presented"]
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
    (output / "acceptance.json").write_text(json.dumps(report))
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(run, first_interval=1)
