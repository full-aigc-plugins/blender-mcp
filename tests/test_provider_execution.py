import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from partme_blender_mcp.harness.provider_execution import record_generation_result
from partme_blender_mcp.harness.provider_tasks import ProviderTaskRegistry


class NativeGenerationTests(unittest.TestCase):
    def test_official_rodin_create_prefers_subscription_key_over_task_uuid(self):
        registry = ProviderTaskRegistry()
        task = record_generation_result('create_rodin_job', {}, {
            'uuid': 'download-task-uuid',
            'jobs': {'subscription_key': 'poll-subscription-key'},
        }, registry=registry)
        self.assertEqual(task['taskId'], 'poll-subscription-key')

    def test_create_poll_complete_updates_ui_registry(self):
        registry = ProviderTaskRegistry()
        task = record_generation_result('create_hunyuan_job', {}, {'JobId': 'job'}, registry=registry)
        self.assertEqual(task['state'], 'generating')
        task = record_generation_result('poll_hunyuan_job_status', {'job_id': 'job'},
            {'Status': 'RUNNING', 'Progress': 68}, registry=registry)
        self.assertEqual(task['progress'], .68)
        task = record_generation_result('poll_hunyuan_job_status', {'job_id': 'job'},
            {'Status': 'DONE'}, registry=registry)
        self.assertEqual(task['state'], 'completed')

    def test_partial_rodin_completion_does_not_complete_whole_job(self):
        task = record_generation_result('poll_rodin_job_status', {'subscription_key': 'job'},
            {'status_list': ['Done', 'Processing']}, registry=ProviderTaskRegistry())
        self.assertEqual(task['state'], 'generating')

    def test_cancelled_task_stays_cancelled_after_native_poll(self):
        registry = ProviderTaskRegistry()
        record_generation_result('create_rodin_job', {}, {'subscription_key': 'job'}, registry=registry)
        registry.request_cancel('hyper3d', 'job')
        task = record_generation_result('poll_rodin_job_status', {'subscription_key': 'job'},
            {'status_list': ['Done']}, registry=registry)
        self.assertEqual(task['state'], 'cancelled')

    def test_late_running_poll_does_not_reopen_completed_generation(self):
        registry = ProviderTaskRegistry()
        record_generation_result('poll_hunyuan_job_status', {'job_id': 'job'},
            {'Response': {'Status': 'DONE'}}, registry=registry)
        task = record_generation_result('poll_hunyuan_job_status', {'job_id': 'job'},
            {'Response': {'Status': 'RUN'}}, registry=registry)
        self.assertEqual(task['state'], 'completed')
        self.assertEqual(task['progress'], 1)
