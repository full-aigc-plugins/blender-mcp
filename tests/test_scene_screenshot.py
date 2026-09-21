"""可靠截图必须恢复 Blender 状态并产生不可变图片回执。"""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from partme_blender_mcp.harness.errors import HarnessError
from partme_blender_mcp.harness.scene_screenshot import SceneScreenshot


def png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"fixture"


class FakeScene:
    def __init__(self):
        self.camera = object()
        self.frame_current = 17
        self.render = SimpleNamespace(
            filepath="original.png",
            resolution_x=1920,
            resolution_y=1080,
            resolution_percentage=50,
            image_settings=SimpleNamespace(file_format="JPEG"),
        )

    def frame_set(self, frame):
        self.frame_current = frame


class SceneScreenshotTests(unittest.TestCase):
    def subject(self, root: Path, *, fail=False):
        scene = FakeScene()

        def render(*, write_still):
            self.assertTrue(write_still)
            Path(scene.render.filepath).write_bytes(png(scene.render.resolution_x, scene.render.resolution_y))
            if fail:
                raise RuntimeError("fixture render failed")

        bpy = SimpleNamespace(
            context=SimpleNamespace(scene=scene),
            ops=SimpleNamespace(render=SimpleNamespace(render=render)),
        )
        return SceneScreenshot(bpy, root), scene

    def test_success_restores_state_and_returns_complete_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subject, scene = self.subject(root)
            before = (scene.camera, scene.frame_current, scene.render.filepath,
                      scene.render.resolution_x, scene.render.resolution_y,
                      scene.render.resolution_percentage, scene.render.image_settings.file_format)

            result = subject.capture({"path": "visual/round-1.png", "width": 640, "height": 360},
                                     scene_revision=7)

            self.assertEqual(before, (scene.camera, scene.frame_current, scene.render.filepath,
                                     scene.render.resolution_x, scene.render.resolution_y,
                                     scene.render.resolution_percentage, scene.render.image_settings.file_format))
            self.assertEqual(result["sceneRevision"], 7)
            self.assertEqual(result["sourceCommand"], "scene.screenshot")
            self.assertEqual(result["mediaType"], "image/png")
            self.assertEqual(result["width"], 640)
            self.assertEqual(result["height"], 360)
            self.assertEqual(len(result["sha256"]), 64)
            self.assertGreater(result["bytes"], 0)
            self.assertEqual(result["restoration"]["status"], "confirmed")

    def test_failure_restores_state_and_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            subject, scene = self.subject(Path(directory), fail=True)
            before = (scene.camera, scene.frame_current, scene.render.filepath,
                      scene.render.resolution_x, scene.render.resolution_y,
                      scene.render.resolution_percentage, scene.render.image_settings.file_format)
            with self.assertRaisesRegex(RuntimeError, "fixture render failed"):
                subject.capture({"path": "failed.png"}, scene_revision=0)
            self.assertEqual(before, (scene.camera, scene.frame_current, scene.render.filepath,
                                     scene.render.resolution_x, scene.render.resolution_y,
                                     scene.render.resolution_percentage, scene.render.image_settings.file_format))

    def test_absolute_escape_existing_and_invalid_dimensions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subject, _ = self.subject(root)
            (root / "exists.png").write_bytes(png(1, 1))
            cases = (
                {"path": str(root / "absolute.png")},
                {"path": "../escape.png"},
                {"path": "exists.png"},
                {"path": "bad.gif"},
                {"path": "bad.png", "width": 0},
                {"path": "bad.png", "height": 9000},
            )
            for arguments in cases:
                with self.subTest(arguments=arguments), self.assertRaises(HarnessError):
                    subject.capture(arguments, scene_revision=0)


if __name__ == "__main__":
    unittest.main()
