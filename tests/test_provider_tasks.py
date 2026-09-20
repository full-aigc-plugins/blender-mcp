import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from partme_blender_mcp.harness.provider_tasks import (  # noqa: E402
    ProviderTaskError,
    ProviderTaskRegistry,
)
from partme_blender_mcp.harness.execution_policy import ExecutionPolicy, ExecutionPolicyError  # noqa: E402


class ProviderTaskRegistryTests(unittest.TestCase):
    def test_generation_lifecycle_and_local_cancel_are_structured(self):
        registry = ProviderTaskRegistry()
        started = registry.update({
            "operation": "start",
            "providerId": "hunyuan3d",
            "taskId": "job-42",
            "state": "generating",
            "progress": 0.25,
            "stage": "正在生成模型",
            "cancelSupported": False,
        })
        self.assertEqual(started["state"], "generating")

        cancelled = registry.request_cancel("hunyuan3d", "job-42")
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertTrue(cancelled["cancelRequested"])
        self.assertTrue(cancelled["remoteMayContinue"])
        self.assertIn("远端任务可能仍在运行", cancelled["message"])
        self.assertEqual(registry.status("hunyuan3d", "job-42"), cancelled)

    def test_progress_and_terminal_state_validation(self):
        registry = ProviderTaskRegistry()
        with self.assertRaises(ProviderTaskError):
            registry.update({
                "operation": "start", "providerId": "bad id", "taskId": "task",
                "state": "generating",
            })
        with self.assertRaises(ProviderTaskError):
            registry.update({
                "operation": "start", "providerId": "hyper3d", "taskId": "task",
                "state": "generating", "progress": 1.5,
            })

        registry.update({
            "operation": "start", "providerId": "hyper3d", "taskId": "task",
            "state": "generating",
        })
        completed = registry.update({
            "operation": "finish", "providerId": "hyper3d", "taskId": "task",
            "state": "completed", "progress": 1.0, "stage": "生成完成",
        })
        self.assertEqual(completed["state"], "completed")
        self.assertFalse(completed["active"])

    def test_status_and_list_operations_support_plugin_bridge(self):
        registry = ProviderTaskRegistry()
        registry.update({
            "operation": "start", "providerId": "hyper3d", "taskId": "task-a",
            "state": "submitting",
        })
        self.assertEqual(registry.control({
            "operation": "status", "providerId": "hyper3d", "taskId": "task-a",
        })["taskId"], "task-a")
        self.assertEqual(len(registry.control({"operation": "list"})["tasks"]), 1)
        cancelled = registry.control({
            "operation": "cancel", "providerId": "hyper3d", "taskId": "task-a",
        })
        self.assertEqual(cancelled["state"], "cancelled")


class ProviderAssetStrategyTests(unittest.TestCase):
    def test_automatic_asset_strategy_is_audited_and_defaults_on(self):
        policy = ExecutionPolicy.from_dict({
            "mode": "auto_with_budget",
            "approvedOutputRoot": "/tmp/partme-output",
        })
        self.assertEqual(policy.asset_strategy, "auto_search_generate")
        self.assertEqual(policy.to_audit_dict()["assetStrategy"], "auto_search_generate")

    def test_unknown_asset_strategy_is_rejected(self):
        with self.assertRaises(ExecutionPolicyError):
            ExecutionPolicy.from_dict({"mode": "interactive", "assetStrategy": "anything_goes"})


if __name__ == "__main__":
    unittest.main()
class CancelledTaskInvariantTests(unittest.TestCase):
    def test_late_updates_cannot_restart_cancelled_task(self):
        registry = ProviderTaskRegistry()
        registry.update({'operation': 'start', 'providerId': 'hyper3d', 'taskId': 'job', 'state': 'generating'})
        cancelled = registry.request_cancel('hyper3d', 'job')
        for operation, state in [('update', 'generating'), ('finish', 'completed'), ('start', 'generating')]:
            result = registry.update({'operation': operation, 'providerId': 'hyper3d', 'taskId': 'job', 'state': state})
            self.assertEqual(result, cancelled)
