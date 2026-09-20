"""供应商提交阶段必须后台运行，并保持取消与单次提交语义。"""
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from partme_blender_mcp.harness.provider_submission import ProviderSubmitter
from partme_blender_mcp.harness.provider_tasks import ProviderTaskRegistry


class ProviderSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tasks = ProviderTaskRegistry()
        self.submitter = ProviderSubmitter(
            self.tasks, id_factory=lambda: "submit_local",
        )

    def tearDown(self):
        self.submitter.close()

    def test_slow_submit_returns_immediately_and_cancel_discards_late_result(self):
        entered, release = threading.Event(), threading.Event()
        callbacks = []

        def submit():
            entered.set()
            release.wait(2)
            return {"subscription_key": "remote-job"}

        task = self.submitter.submit(
            "hyper3d", submit,
            remote_id=lambda result: result["subscription_key"],
            on_submitted=lambda *args: callbacks.append(args),
        )
        self.assertEqual(task["state"], "submitting")
        self.assertEqual(task["taskId"], "submit_local")
        self.assertTrue(entered.wait(1))
        self.tasks.request_cancel("hyper3d", "submit_local")
        release.set()
        self.submitter.join("hyper3d", "submit_local", timeout=2)

        self.assertEqual(self.tasks.status("hyper3d", "submit_local")["state"], "cancelled")
        self.assertEqual(callbacks, [])

    def test_success_records_remote_id_then_starts_follow_up(self):
        completed = threading.Event()
        callbacks = []

        task = self.submitter.submit(
            "hunyuan3d", lambda: {"Response": {"JobId": "remote-42"}},
            remote_id=lambda result: result["Response"]["JobId"],
            on_submitted=lambda local_id, remote_id, result: (
                callbacks.append((local_id, remote_id, result)), completed.set()),
        )
        self.assertEqual(task["state"], "submitting")
        self.assertTrue(completed.wait(1))
        self.submitter.join("hunyuan3d", "submit_local", timeout=2)

        current = self.tasks.status("hunyuan3d", "submit_local")
        self.assertEqual(current["state"], "generating")
        self.assertEqual(current["remoteTaskId"], "remote-42")
        self.assertEqual(callbacks[0][:2], ("submit_local", "remote-42"))
        self.assertEqual(
            self.tasks.find_by_remote("hunyuan3d", "remote-42")["taskId"],
            "submit_local",
        )

    def test_failure_is_terminal_and_does_not_expose_exception_text(self):
        def submit():
            raise RuntimeError("secret signed URL")

        self.submitter.submit(
            "hyper3d", submit,
            remote_id=lambda result: result["id"],
            on_submitted=lambda *_args: self.fail("failed submission must not continue"),
        )
        self.submitter.join("hyper3d", "submit_local", timeout=2)
        task = self.tasks.status("hyper3d", "submit_local")
        self.assertEqual(task["state"], "failed")
        self.assertEqual(task["message"], "供应商提交失败或结果未知；请检查任务，勿自动重复提交")
        self.assertNotIn("secret", str(task))


if __name__ == "__main__":
    unittest.main()
