import struct
import tempfile
import threading
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from partme_blender_mcp.harness.local_generation import LocalGeneration
from partme_blender_mcp.harness.provider_tasks import ProviderTaskRegistry
from partme_blender_mcp.harness.errors import HarnessError


class LocalGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.tasks = ProviderTaskRegistry()
        self.http = Mock()
        self.service = LocalGeneration(self.tasks, self.http)
        self.response = Mock(status_code=200)
        self.response.__enter__ = Mock(return_value=self.response)
        self.response.__exit__ = Mock(return_value=False)
        self.response.iter_content.return_value = [struct.pack('<4sII', b'glTF', 2, 12)]
        self.http.post.return_value = self.response

    def tearDown(self):
        self.service.close()
        for job in self.service._jobs.values():
            job['thread'].join(2)
        self.temp.cleanup()

    def submit(self):
        result = self.service.submit('http://127.0.0.1:8080', {'text_prompt': 'chair'}, {}, [self.root])
        return result['JobId']

    def test_stages_without_import_and_returns_authorized_path(self):
        task_id = self.submit()
        self.service._jobs[task_id]['thread'].join(2)
        result = self.service.status(task_id)
        self.assertEqual(result['Status'], 'DONE')
        self.assertTrue(Path(result['path']).is_relative_to(self.root))
        self.assertTrue(Path(result['path']).is_file())
        self.assertFalse(self.http.post.call_args.kwargs['allow_redirects'])

    def test_requires_authorization_before_request(self):
        with self.assertRaises(HarnessError):
            self.service.submit('http://127.0.0.1:8080', {'text_prompt': 'chair'}, {}, [])
        self.http.post.assert_not_called()

    def test_cancel_inflight_discards_body_and_result(self):
        entered, release = threading.Event(), threading.Event()
        def post(*args, **kwargs):
            entered.set()
            release.wait(2)
            return self.response
        self.http.post.side_effect = post
        task_id = self.submit()
        self.assertTrue(entered.wait(1))
        self.tasks.request_cancel('hunyuan3d', task_id)
        release.set()
        self.service._jobs[task_id]['thread'].join(2)
        self.assertEqual(self.service.status(task_id)['Status'], 'CANCELLED')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_or_oversized_response_is_not_published(self):
        for data in (b'<html>secret</html>', b'x' * 32):
            self.service.max_bytes = 20
            self.response.iter_content.return_value = [data]
            task_id = self.submit()
            self.service._jobs[task_id]['thread'].join(2)
            result = self.service.status(task_id)
            self.assertEqual(result['Status'], 'FAIL')
            self.assertIsNone(result['path'])
            self.assertNotIn('secret', str(result))
            self.assertEqual(list(self.root.iterdir()), [])
