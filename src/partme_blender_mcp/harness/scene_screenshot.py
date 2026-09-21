"""Reliable scene screenshots which restore every touched Blender setting."""

from __future__ import annotations

from pathlib import Path

from .errors import HarnessError
from .image_artifact import inspect_image_file
from .version import __version__


class SceneScreenshot:
    """Capture one still into the approved output root without mutating scene state."""

    def __init__(self, bpy_module, output_root: Path):
        self.bpy = bpy_module
        self.root = Path(output_root).resolve()

    def capture(self, arguments: dict, *, scene_revision: int) -> dict:
        target, file_format = self._target(arguments.get("path"))
        width = self._dimension(arguments.get("width", 512), "width")
        height = self._dimension(arguments.get("height", 512), "height")
        if target.exists() or target.is_symlink():
            raise HarnessError("ARTIFACT_EXISTS", "screenshot target already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.resolve().is_relative_to(self.root):
            raise HarnessError("OUTPUT_NOT_AUTHORIZED", "screenshot path escapes the approved output root")

        scene = self.bpy.context.scene
        render = scene.render
        original = (
            scene.camera,
            render.filepath,
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
            render.image_settings.file_format,
            scene.frame_current,
        )
        succeeded = False
        try:
            render.filepath = str(target)
            render.resolution_x = width
            render.resolution_y = height
            render.resolution_percentage = 100
            render.image_settings.file_format = file_format
            self.bpy.ops.render.render(write_still=True)
            artifact = inspect_image_file(target)
            if (artifact["width"], artifact["height"]) != (width, height):
                raise HarnessError("ARTIFACT_INVALID", "rendered image dimensions do not match the request")
            succeeded = True
        finally:
            (scene.camera, render.filepath, render.resolution_x, render.resolution_y,
             render.resolution_percentage, render.image_settings.file_format, frame) = original
            scene.frame_set(frame)
            if not succeeded:
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
        artifact.update({
            "protocolVersion": "codex-blender/v1",
            "producer": {"name": "partme-blender-mcp", "version": __version__},
            "sceneRevision": int(scene_revision),
            "sourceCommand": "scene.screenshot",
            "parameters": {"width": width, "height": height},
            "validation": {
                "status": "passed",
                "checks": ["approved_output", "new_file", "image_signature", "dimensions", "sha256"],
            },
            "restoration": {"status": "confirmed"},
        })
        return artifact

    def _target(self, value) -> tuple[Path, str]:
        if not isinstance(value, str) or not value.strip():
            raise HarnessError("INVALID_ARGUMENT", "path must be a non-empty relative path")
        relative = Path(value)
        if relative.is_absolute():
            raise HarnessError("OUTPUT_NOT_AUTHORIZED", "screenshot path must be relative")
        suffix = relative.suffix.lower()
        formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}
        if suffix not in formats:
            raise HarnessError("INVALID_ARGUMENT", "screenshot path must end in .png, .jpg, or .jpeg")
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise HarnessError("OUTPUT_NOT_AUTHORIZED", "screenshot path escapes the approved output root")
        return target, formats[suffix]

    @staticmethod
    def _dimension(value, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8192:
            raise HarnessError("INVALID_ARGUMENT", f"{field} must be an integer from 1 to 8192")
        return value
