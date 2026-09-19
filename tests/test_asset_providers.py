import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from partme_blender_mcp.harness.commands.asset import AssetCommands
from partme_blender_mcp.harness.errors import HarnessError
from partme_blender_mcp.harness.path_policy import PathPolicy


class FakeBpy:
    class data:
        objects = []


class FakeResponse:
    def __init__(self, body=b"", headers=None, url="https://provider.example/model.glb"):
        self.body = body
        self.headers = headers or {"Content-Length": str(len(body))}
        self.url = url

    def read(self, size=-1):
        size = len(self.body) if size is None or size < 0 else size
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url


class NativeProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.commands = AssetCommands(FakeBpy, asset_policy=PathPolicy([self.root]))

    def tearDown(self):
        self.temp.cleanup()

    def test_polypizza_search_requires_plugin_owned_environment_key(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(HarnessError) as caught:
            self.commands.polypizza_search({"query": "chair"})
        self.assertEqual(caught.exception.code, "POLYPIZZA_KEY_MISSING")

    def test_polypizza_download_stages_file_and_license_without_importing_scene(self):
        detail = {"ID": "abc", "Title": "Chair", "Creator": {"Username": "maker"},
                  "Licence": 0, "Download": "https://static.poly.pizza/abc.glb"}
        responses = [FakeResponse(json.dumps(detail).encode()), FakeResponse(b"glTF-bytes")]
        with mock.patch.dict(os.environ, {"POLYPIZZA_API_KEY": "test"}), \
             mock.patch("urllib.request.urlopen", side_effect=responses):
            result = self.commands.polypizza_download({"modelId": "abc"})["result"]
        self.assertEqual(Path(result["path"]).read_bytes(), b"glTF-bytes")
        self.assertTrue(Path(result["sidecar"]).is_file())
        self.assertEqual(FakeBpy.data.objects, [])

    def test_fetch_url_rejects_unknown_host_and_writes_to_authorized_root(self):
        with self.assertRaises(HarnessError):
            self.commands.fetch_url({"url": "https://evil.example/model.glb"})
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"asset")):
            result = self.commands.fetch_url({
                "url": "https://dl.polyhaven.org/file/model.glb",
            })["result"]
        self.assertTrue(Path(result["path"]).is_relative_to(self.root))

    def test_generated_result_is_staged_under_provider_without_importing_scene(self):
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"generated")):
            result = self.commands.fetch_generated({
                "providerId": "hyper3d",
                "url": "https://provider.example/model.glb",
            })["result"]
        path = Path(result["path"])
        self.assertTrue(path.is_relative_to(self.root / "generated" / "hyper3d"))
        self.assertEqual(path.read_bytes(), b"generated")
        self.assertEqual(FakeBpy.data.objects, [])


if __name__ == "__main__":
    unittest.main()
