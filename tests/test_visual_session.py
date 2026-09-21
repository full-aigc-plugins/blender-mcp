"""Visual state writes are standard-risk operations without scene revision mutation."""

from __future__ import annotations

import unittest

from partme_blender_mcp.harness.session import HarnessSession


class VisualSessionTests(unittest.TestCase):
    def request(self, command: str, request_id: str) -> dict:
        return {
            "protocolVersion": "codex-blender/v1",
            "sessionId": "visual-session",
            "requestId": request_id,
            "transactionId": "visual-state",
            "expectedSceneRevision": 0,
            "command": command,
            "arguments": {},
        }

    def test_screenshot_and_visual_state_writes_do_not_advance_scene_revision(self):
        dispatched = []

        def dispatch(command, arguments):
            dispatched.append((command, arguments))
            return {"changedObjects": [], "result": {"ok": True}}

        session = HarnessSession("visual-session", dispatch=dispatch)
        for index, command in enumerate((
            "scene.screenshot", "visual_loop.create", "visual_loop.record_capture",
            "visual_loop.record_verdict", "visual_loop.cancel",
        )):
            response = session.handle(self.request(command, f"visual-{index}"))
            self.assertEqual(response["status"], "succeeded")
            self.assertEqual(response["sceneRevision"], 0)
        self.assertEqual([item[0] for item in dispatched], [
            "scene.screenshot", "visual_loop.create", "visual_loop.record_capture",
            "visual_loop.record_verdict", "visual_loop.cancel",
        ])


if __name__ == "__main__":
    unittest.main()
