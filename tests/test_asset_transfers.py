"""素材网络任务必须异步、可取消，并且不泄漏晚到结果。"""

import threading
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from partme_blender_mcp.harness.asset_transfers import AssetTransferRunner
from partme_blender_mcp.harness.provider_tasks import ProviderTaskRegistry


class AssetTransferRunnerTests(unittest.TestCase):
    def setUp(self):
        self.registry = ProviderTaskRegistry()
        self.runner = AssetTransferRunner(
            self.registry, id_factory=lambda: "asset_fixture",
        )

    def tearDown(self):
        self.runner.close()

    def test_submit_returns_immediately_and_exposes_completed_result(self):
        entered = threading.Event()
        release = threading.Event()
        worker_ids = []

        def transfer(cancelled):
            worker_ids.append(threading.get_ident())
            entered.set()
            release.wait(2)
            self.assertFalse(cancelled())
            return {"path": "/approved/model.glb", "bytes": 5}

        task = self.runner.submit("polyhaven", transfer)
        self.assertEqual(task["state"], "downloading")
        self.assertTrue(task["cancelSupported"])
        self.assertTrue(entered.wait(1))
        self.assertNotEqual(worker_ids, [threading.get_ident()])

        release.set()
        self.runner.join("polyhaven", task["taskId"], timeout=2)
        result = self.runner.result("polyhaven", task["taskId"])
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["result"]["path"], "/approved/model.glb")

    def test_cancelled_transfer_discards_late_result(self):
        entered = threading.Event()
        release = threading.Event()

        def transfer(cancelled):
            entered.set()
            release.wait(2)
            return {"cancelObserved": cancelled()}

        task = self.runner.submit("hyper3d", transfer)
        self.assertTrue(entered.wait(1))
        cancelled = self.registry.request_cancel("hyper3d", task["taskId"])
        self.assertFalse(cancelled["remoteMayContinue"])
        release.set()
        self.runner.join("hyper3d", task["taskId"], timeout=2)

        result = self.runner.result("hyper3d", task["taskId"])
        self.assertEqual(result["state"], "cancelled")
        self.assertNotIn("result", result)

    def test_close_prevents_late_result_write(self):
        entered = threading.Event()
        release = threading.Event()

        def transfer(_cancelled):
            entered.set()
            release.wait(2)
            return {"late": True}

        task = self.runner.submit("polypizza", transfer)
        self.assertTrue(entered.wait(1))
        self.runner.close()
        release.set()
        self.runner.join("polypizza", task["taskId"], timeout=2)
        self.assertNotIn("result", self.runner.result("polypizza", task["taskId"]))


if __name__ == "__main__":
    unittest.main()
