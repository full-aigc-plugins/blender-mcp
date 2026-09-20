"""供应商只读查询必须离开 Blender 主线程，并支持结果查询与本地终止。"""

import threading
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from partme_blender_mcp.harness.provider_queries import ProviderQueryRunner
from partme_blender_mcp.harness.provider_tasks import ProviderTaskRegistry


class ProviderQueryRunnerTests(unittest.TestCase):
    def setUp(self):
        self.registry = ProviderTaskRegistry()
        self.runner = ProviderQueryRunner(self.registry, id_factory=lambda: "query_fixture")

    def tearDown(self):
        self.runner.close()

    def test_submit_returns_before_slow_query_and_exposes_result(self):
        entered = threading.Event()
        release = threading.Event()
        worker_ids = []

        def query():
            worker_ids.append(threading.get_ident())
            entered.set()
            release.wait(2)
            return {"assets": {"chair": {"name": "Chair"}}}

        task = self.runner.submit("polyhaven", query)
        self.assertEqual(task["state"], "querying")
        self.assertTrue(entered.wait(1))
        self.assertNotEqual(worker_ids, [threading.get_ident()])
        self.assertEqual(self.runner.result("polyhaven", task["taskId"])["state"], "querying")

        release.set()
        self.runner.join("polyhaven", task["taskId"], timeout=2)
        result = self.runner.result("polyhaven", task["taskId"])
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["result"]["assets"]["chair"]["name"], "Chair")

    def test_cancelled_query_discards_late_result(self):
        entered = threading.Event()
        release = threading.Event()

        def query():
            entered.set()
            release.wait(2)
            return {"secretLateResult": True}

        task = self.runner.submit("sketchfab", query)
        self.assertTrue(entered.wait(1))
        self.registry.request_cancel("sketchfab", task["taskId"])
        release.set()
        self.runner.join("sketchfab", task["taskId"], timeout=2)

        result = self.runner.result("sketchfab", task["taskId"])
        self.assertEqual(result["state"], "cancelled")
        self.assertNotIn("result", result)


if __name__ == "__main__":
    unittest.main()
