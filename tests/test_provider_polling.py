"""后台轮询不得阻塞调用方、复活取消任务或泄漏网络异常。"""
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from partme_blender_mcp.harness.provider_tasks import ProviderTaskRegistry
from partme_blender_mcp.harness.provider_polling import ProviderPoller


class PollingTests(unittest.TestCase):
    def setUp(self):
        self.tasks = ProviderTaskRegistry()
        self.tasks.update({'operation': 'start', 'providerId': 'hyper3d',
                           'taskId': 'job', 'state': 'generating'})
        self.poller = ProviderPoller(self.tasks, interval=.01, max_errors=2)

    def tearDown(self):
        self.poller.close()

    def test_slow_query_does_not_block_start_or_cancel(self):
        entered, release = threading.Event(), threading.Event()
        def query():
            entered.set()
            release.wait(2)
            return {'status_list': ['Done']}
        worker = self.poller.start('poll_rodin_job_status', {'subscription_key': 'job'}, query)
        try:
            self.assertTrue(entered.wait(1))
            self.tasks.request_cancel('hyper3d', 'job')
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.tasks.status('hyper3d', 'job')['state'], 'cancelled')

    def test_completes_without_manual_poll_and_deduplicates(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def query():
            calls.append(1)
            entered.set()
            release.wait(2)
            return {'status_list': ['Done']}
        worker = self.poller.start('poll_rodin_job_status', {'subscription_key': 'job'}, query)
        self.assertTrue(entered.wait(1))
        self.assertIs(worker, self.poller.start('poll_rodin_job_status', {'subscription_key': 'job'}, query))
        release.set()
        worker.join(2)
        self.assertEqual(calls, [1])
        self.assertEqual(self.tasks.status('hyper3d', 'job')['state'], 'completed')

    def test_retries_are_bounded_and_errors_are_sanitized(self):
        calls = []
        def query():
            calls.append(1)
            raise ValueError('secret-key signed-url')
        worker = self.poller.start('poll_rodin_job_status', {'subscription_key': 'job'}, query)
        worker.join(2)
        task = self.tasks.status('hyper3d', 'job')
        self.assertEqual(len(calls), 2)
        self.assertEqual(task['state'], 'failed')
        self.assertNotIn('secret-key', str(task))
        self.assertIn('远端状态未知', task['message'])

    def test_shutdown_discards_inflight_result(self):
        entered, release = threading.Event(), threading.Event()
        def query():
            entered.set()
            release.wait(2)
            return {'status_list': ['Done']}
        worker = self.poller.start('poll_rodin_job_status', {'subscription_key': 'job'}, query)
        self.assertTrue(entered.wait(1))
        self.poller.close()
        release.set()
        worker.join(2)
        self.assertEqual(self.tasks.status('hyper3d', 'job')['state'], 'generating')
        with self.assertRaises(RuntimeError):
            self.poller.start('poll_rodin_job_status', {'subscription_key': 'job'}, query)

    def test_malformed_status_responses_exhaust_bounded_retries(self):
        for response in ({}, {'status_list': []}, {'status_list': [None]},
                         {'status': ''}, {'status': {'unexpected': 'Done'}},
                         {'Response': {'RequestId': 'request-only'}}):
            with self.subTest(response=response):
                tasks = ProviderTaskRegistry()
                tasks.update({'operation': 'start', 'providerId': 'hyper3d',
                              'taskId': 'malformed', 'state': 'generating'})
                poller = ProviderPoller(tasks, interval=.001, max_errors=2)
                calls = []
                def query(calls=calls, response=response):
                    calls.append(1)
                    return response
                worker = poller.start('poll_rodin_job_status',
                                      {'subscription_key': 'malformed'}, query)
                try:
                    worker.join(.2)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(len(calls), 2)
                    task = tasks.status('hyper3d', 'malformed')
                    self.assertEqual(task['state'], 'failed')
                    self.assertIn('远端状态未知', task['message'])
                finally:
                    poller.close()
                    worker.join(1)

    def test_duration_limit_stops_before_next_request(self):
        self.poller.max_duration = 0
        calls = []
        worker = self.poller.start('poll_rodin_job_status', {'subscription_key': 'job'}, lambda: calls.append(1))
        worker.join(2)
        self.assertEqual(calls, [])
        self.assertEqual(self.tasks.status('hyper3d', 'job')['state'], 'failed')
