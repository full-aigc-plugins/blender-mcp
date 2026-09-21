"""远程 MCP 视觉结果必须携带图片内容而不是仅暴露主机路径。"""

from __future__ import annotations

import base64
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from partme_blender_mcp.harness.mcp_adapter import McpAdapter


def png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 2, 1) + b"fixture"


class Bridge:
    def __init__(self, root: Path, response: dict):
        self.root = root
        self.response = response

    def status(self):
        return {"sceneRevision": 3}

    def authorized_output_root(self):
        return self.root

    def call(self, *_args, **_kwargs):
        return self.response


class McpVisualContentTests(unittest.TestCase):
    def response(self, path: Path, digest: str) -> dict:
        return {
            "status": "succeeded", "sceneRevision": 3,
            "result": {"artifact": {
                "path": str(path), "sha256": digest, "bytes": path.stat().st_size,
                "mediaType": "image/png", "width": 2, "height": 1,
                "sourceCommand": "scene.screenshot",
            }},
        }

    def test_screenshot_returns_text_structured_content_and_image_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "screen.png"
            body = png()
            path.write_bytes(body)
            adapter = McpAdapter(bridge=Bridge(root, self.response(path, hashlib.sha256(body).hexdigest())))
            result = adapter.call_tool(
                "blender_scene_screenshot", {"path": "screen.png", "_transactionId": "visual-1"},
            )
            self.assertFalse(result["isError"])
            self.assertEqual(result["structuredContent"]["result"]["artifact"]["width"], 2)
            images = [item for item in result["content"] if item["type"] == "image"]
            self.assertEqual(len(images), 1)
            self.assertEqual(images[0]["mimeType"], "image/png")
            self.assertEqual(base64.b64decode(images[0]["data"]), body)

    def test_tampered_or_outside_artifact_is_not_returned(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            path = root / "screen.png"
            path.write_bytes(png())
            for candidate, digest in (
                (path, "0" * 64),
                (Path(outside) / "screen.png", hashlib.sha256(png()).hexdigest()),
            ):
                candidate.write_bytes(png())
                adapter = McpAdapter(bridge=Bridge(root, self.response(candidate, digest)))
                result = adapter.call_tool(
                    "blender_scene_screenshot", {"path": "screen.png", "_transactionId": "visual-1"},
                )
                self.assertTrue(result["isError"])
                self.assertEqual(result["structuredContent"]["error"]["code"], "IMAGE_ARTIFACT_CHANGED")

    def test_preview_returns_all_verified_views_as_image_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = png()
            views = []
            for name in ("camera", "front", "side", "top"):
                path = root / f"{name}.png"
                path.write_bytes(body)
                views.append({"name": name, "path": str(path), "sha256": hashlib.sha256(body).hexdigest()})
            response = {
                "status": "succeeded", "sceneRevision": 3,
                "result": {"milestone": {"views": views}},
            }
            adapter = McpAdapter(bridge=Bridge(root, response))
            result = adapter.call_tool("blender_preview_capture", {
                "snapshotId": "snapshot-1", "_transactionId": "visual-1",
            })
            self.assertFalse(result["isError"])
            self.assertEqual(len([item for item in result["content"] if item["type"] == "image"]), 4)


if __name__ == "__main__":
    unittest.main()
