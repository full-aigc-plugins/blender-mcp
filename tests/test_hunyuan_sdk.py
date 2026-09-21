"""腾讯混元 3D 官方 SDK 适配边界。"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from partme_blender_mcp.harness.errors import HarnessError


MODULE_PATH = Path(__file__).parents[1] / "addon/partme_blender_mcp/hunyuan_sdk.py"


class _Credential:
    def __init__(self, secret_id, secret_key):
        self.values = secret_id, secret_key


class _HttpProfile:
    pass


class _ClientProfile:
    def __init__(self, httpProfile=None):
        self.httpProfile = httpProfile


class _Request:
    def from_json_string(self, raw):
        self.payload = json.loads(raw)


class _Response:
    def to_json_string(self):
        return json.dumps({"JobId": "job-1", "RequestId": "request-1"})


class _Models:
    SubmitHunyuanTo3DProJobRequest = _Request


class _Client:
    instances = []

    def __init__(self, credential, region, profile):
        self.credential = credential
        self.region = region
        self.profile = profile
        self.request = None
        self.instances.append(self)

    def SubmitHunyuanTo3DProJob(self, request):
        self.request = request
        return _Response()


class _CommonClient:
    instances = []

    def __init__(self, service, version, credential, region, profile):
        self.values = service, version, credential, region, profile
        self.instances.append(self)

    def call_json(self, action, payload):
        self.action = action
        self.payload = payload
        return {"Response": {"JobId": "international-1", "RequestId": "request-2"}}


class HunyuanSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "partme_blender_mcp.hunyuan_sdk", MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        _Client.instances.clear()
        _CommonClient.instances.clear()
        self.sdk = SimpleNamespace(
            Credential=_Credential,
            CommonClient=_CommonClient,
            Ai3dClient=_Client,
            models=_Models,
            ClientProfile=_ClientProfile,
            HttpProfile=_HttpProfile,
            sdk_exception=RuntimeError,
        )

    def test_invocation_uses_pinned_profile_and_wraps_response(self):
        with patch.object(self.module, "_load_sdk", return_value=self.sdk):
            result = self.module.invoke_hunyuan_sdk(
                "SubmitHunyuanTo3DProJob", {"Prompt": "chair"},
                {"service": "ai3d", "version": "2025-05-13",
                 "region": "ap-guangzhou"}, "fixture-id", "fixture-key")
        client = _Client.instances[0]
        self.assertEqual(client.credential.values, ("fixture-id", "fixture-key"))
        self.assertEqual(client.region, "ap-guangzhou")
        self.assertEqual(client.profile.httpProfile.endpoint, "ai3d.tencentcloudapi.com")
        self.assertEqual(client.profile.httpProfile.reqTimeout, 30)
        self.assertEqual(client.profile.httpProfile.reqMethod, "POST")
        self.assertEqual(client.request.payload, {"Prompt": "chair"})
        self.assertEqual(result, {"Response": {"JobId": "job-1", "RequestId": "request-1"}})

    def test_international_compatibility_profile_uses_official_common_client(self):
        with patch.object(self.module, "_load_sdk", return_value=self.sdk):
            result = self.module.invoke_hunyuan_sdk(
                "SubmitHunyuanTo3DProJob", {"Prompt": "chair", "EnablePBR": True},
                {"service": "hunyuan", "version": "2023-09-01",
                 "region": "ap-singapore"}, "fixture-id", "fixture-key")
        client = _CommonClient.instances[0]
        self.assertEqual(client.values[:2], ("hunyuan", "2023-09-01"))
        self.assertEqual(client.values[3], "ap-singapore")
        self.assertEqual(client.action, "SubmitHunyuanTo3DProJob")
        self.assertEqual(client.payload, {"Prompt": "chair", "EnablePBR": True})
        self.assertEqual(result["Response"]["JobId"], "international-1")

    def test_unknown_action_is_rejected_before_client_creation(self):
        with patch.object(self.module, "_load_sdk", return_value=self.sdk):
            with self.assertRaises(HarnessError) as caught:
                self.module.invoke_hunyuan_sdk(
                    "UnknownAction", {}, {"service": "ai3d", "version": "2025-05-13",
                    "region": "ap-guangzhou"}, "fixture-id", "fixture-key")
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
        self.assertEqual(_Client.instances, [])

    def test_sdk_failure_is_sanitized_and_never_exposes_secret(self):
        class FailingClient(_Client):
            def SubmitHunyuanTo3DProJob(self, _request):
                raise RuntimeError("fixture-key remote detail")

        self.sdk.Ai3dClient = FailingClient
        with patch.object(self.module, "_load_sdk", return_value=self.sdk):
            with self.assertRaises(HarnessError) as caught:
                self.module.invoke_hunyuan_sdk(
                    "SubmitHunyuanTo3DProJob", {"Prompt": "chair"},
                    {"service": "ai3d", "version": "2025-05-13",
                     "region": "ap-guangzhou"}, "fixture-id", "fixture-key")
        self.assertEqual(caught.exception.code, "PROVIDER_REQUEST_FAILED")
        self.assertNotIn("fixture-key", str(caught.exception))
