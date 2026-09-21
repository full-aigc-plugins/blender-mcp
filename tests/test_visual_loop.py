"""目标锁定与视觉评审状态机契约。"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from partme_blender_mcp.harness.errors import HarnessError
from partme_blender_mcp.harness.visual_loop import VisualLoopStore


def png(width: int = 32, height: int = 24) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"fixture"


class VisualLoopStoreTests(unittest.TestCase):
    def test_uploaded_target_is_locked_and_state_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = png()
            store = VisualLoopStore(root)
            created = store.create({
                "loopId": "chair-review",
                "targetData": base64.b64encode(body).decode("ascii"),
                "minimumScore": 8,
                "maxRounds": 6,
            })
            self.assertEqual(created["target"]["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(created["target"]["width"], 32)
            self.assertNotIn("targetData", json.dumps(created))
            target_path = Path(created["target"]["path"])
            self.assertEqual(target_path.read_bytes(), body)

            reloaded = VisualLoopStore(root).status({"loopId": "chair-review"})
            self.assertEqual(reloaded, created)
            target_path.write_bytes(png(33, 24))
            with self.assertRaises(HarnessError) as caught:
                VisualLoopStore(root).status({"loopId": "chair-review"})
            self.assertEqual(caught.exception.code, "VISUAL_TARGET_CHANGED")

    def test_local_target_requires_an_authorized_root_and_is_copied(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            root = Path(directory)
            allowed = root / "assets"
            allowed.mkdir()
            source = allowed / "reference.png"
            source.write_bytes(png())
            store = VisualLoopStore(root / "output", input_roots=(allowed,))
            created = store.create({"targetPath": str(source)})
            self.assertNotEqual(Path(created["target"]["path"]), source)
            self.assertEqual(Path(created["target"]["path"]).read_bytes(), source.read_bytes())
            outside = Path(external) / "outside.png"
            outside.write_bytes(png())
            with self.assertRaises(HarnessError) as caught:
                store.create({"targetPath": str(outside)})
            self.assertEqual(caught.exception.code, "ASSET_NOT_AUTHORIZED")

    def test_verdict_computes_total_best_round_acceptance_and_transaction_advice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = png()
            store = VisualLoopStore(root)
            state = store.create({"targetData": base64.b64encode(body).decode(), "minimumScore": 8})
            capture = root / "candidate.png"
            capture.write_bytes(body)
            artifact = {
                "path": str(capture), "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body), "mediaType": "image/png", "width": 32, "height": 24,
            }
            round_one = store.record_capture({
                "loopId": state["loopId"], "artifact": artifact, "transactionId": "tx-1",
            })
            judged = store.record_verdict({
                "loopId": state["loopId"], "round": round_one["currentRound"],
                "scores": {"composition": 8, "lighting": 9, "materials": 7, "details": 8},
                "issues": ["minor roughness mismatch"], "nextActions": ["commit current transaction"],
                "judge": {"type": "agent", "name": "fixture"},
            })
            self.assertEqual(judged["history"][0]["verdict"]["total"], 8.0)
            self.assertEqual(judged["bestRound"], 1)
            self.assertEqual(judged["state"], "accepted")
            self.assertEqual(judged["recommendedAction"], "commit")
            self.assertEqual(judged["pendingTransactionId"], "tx-1")

    def test_stall_and_exhaustion_recommend_rollback_and_cancel_is_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = png()
            store = VisualLoopStore(root)
            state = store.create({
                "targetData": base64.b64encode(body).decode(), "minimumScore": 9,
                "maxRounds": 4, "stallWindow": 2, "minimumImprovement": 1,
            })
            for index, score in enumerate((4.0, 4.4, 4.6), start=1):
                capture = root / f"candidate-{index}.png"
                capture.write_bytes(body)
                state = store.record_capture({
                    "loopId": state["loopId"],
                    "artifact": {"path": str(capture), "sha256": hashlib.sha256(body).hexdigest()},
                    "transactionId": f"tx-{index}",
                })
                state = store.record_verdict({
                    "loopId": state["loopId"], "round": index,
                    "scores": {name: score for name in ("composition", "lighting", "materials", "details")},
                    "issues": [], "nextActions": ["revise"], "judge": {"type": "human"},
                })
            self.assertEqual(state["state"], "stalled")
            self.assertEqual(state["recommendedAction"], "rollback")
            with self.assertRaises(HarnessError):
                store.record_capture({"loopId": state["loopId"], "artifact": {}, "transactionId": "tx-4"})

            other = store.create({"targetData": base64.b64encode(body).decode(), "loopId": "cancel-me"})
            cancelled = store.cancel({"loopId": other["loopId"]})
            self.assertEqual(cancelled["state"], "cancelled")
            self.assertEqual(cancelled["recommendedAction"], "rollback")

    def test_invalid_scores_do_not_change_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = png()
            store = VisualLoopStore(root)
            state = store.create({"targetData": base64.b64encode(body).decode()})
            capture = root / "candidate.png"
            capture.write_bytes(body)
            state = store.record_capture({
                "loopId": state["loopId"],
                "artifact": {"path": str(capture), "sha256": hashlib.sha256(body).hexdigest()},
                "transactionId": "tx-invalid",
            })
            with self.assertRaises(HarnessError):
                store.record_verdict({
                    "loopId": state["loopId"], "round": 1,
                    "scores": {"composition": 11, "lighting": 1, "materials": 1, "details": 1},
                    "issues": [], "nextActions": [], "judge": {"type": "agent"},
                })
            self.assertIsNone(store.status({"loopId": state["loopId"]})["history"][0]["verdict"])


if __name__ == "__main__":
    unittest.main()
