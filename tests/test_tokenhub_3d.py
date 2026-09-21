"""TokenHub 3D 传输协议契约。"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


class TokenHub3DTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).parents[1] / "addon/partme_blender_mcp/tokenhub_3d.py"
        spec = importlib.util.spec_from_file_location("partme_blender_mcp.tokenhub_3d", source)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def response(self, payload, status=200):
        response = Mock(status_code=status, json=Mock(return_value=payload))
        wrapper = Mock()
        wrapper.__enter__ = Mock(return_value=response)
        wrapper.__exit__ = Mock(return_value=False)
        return wrapper

    def test_submit_uses_official_endpoint_bearer_and_bounded_request(self):
        http = Mock()
        http.post.return_value = self.response({"id": "job-1", "status": "queued"})
        result = self.module.submit(http, "hy-3d-express", {"prompt": "chair"}, "secret-key")
        self.assertEqual(result["JobId"], "job-1")
        call = http.post.call_args
        self.assertEqual(call.args[0], "https://tokenhub.tencentmaas.com/v1/api/3d/submit")
        self.assertEqual(call.kwargs["json"], {"model": "hy-3d-express", "prompt": "chair"})
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer secret-key")
        self.assertEqual(call.kwargs["timeout"], (5, 30))
        self.assertFalse(call.kwargs["allow_redirects"])

    def test_query_normalizes_regular_and_polygen_results(self):
        http = Mock()
        http.post.return_value = self.response({"status": "completed", "data": [
            {"type": "glb", "url": "https://x.cos.ap-guangzhou.myqcloud.com/a.glb"},
            {"fbx_url": "https://x.cos.ap-guangzhou.myqcloud.com/a.fbx"},
        ]})
        result = self.module.query(http, "hy-3d-3.1", "job-1", "key")
        self.assertEqual(result["Response"]["Status"], "DONE")
        self.assertEqual([item["Type"] for item in result["Response"]["ResultFile3Ds"]], ["GLB", "FBX"])

    def test_key_is_never_returned_or_placed_in_payload(self):
        http = Mock()
        http.post.return_value = self.response({"id": "job-1", "status": "queued"})
        result = self.module.submit(http, "hy-3d-express", {"prompt": "chair"}, "secret-key")
        self.assertNotIn("secret-key", str(result))
        self.assertNotIn("secret-key", str(http.post.call_args.kwargs["json"]))


if __name__ == "__main__":
    unittest.main()
