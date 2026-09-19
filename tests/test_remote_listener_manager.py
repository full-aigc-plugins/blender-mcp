"""Remote listener lifecycle stays real, independent, and credential-safe."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _load_remote():
    spec = importlib.util.spec_from_file_location("partme_remote", ROOT / "addon/partme_blender_mcp/remote.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _preferences(**overrides):
    values = {
        "mcp_python": sys.executable,
        "mcp_entrypoint": "",
        "remote_host": "127.0.0.1",
        "http_port": 19877,
        "sse_port": 19878,
        "http_path": "/mcp",
        "sse_path": "/sse",
        "message_path": "/messages/",
        "public_base_url": "",
        "issuer_url": "",
        "remote_token": "private-token",
        "tls_certfile": "",
        "tls_keyfile": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.returncode = -9


class RemoteListenerManagerTests(unittest.TestCase):
    def setUp(self):
        self.remote = _load_remote()
        self.calls = []

        def factory(command, **kwargs):
            self.calls.append((command, kwargs))
            return FakeProcess(1000 + len(self.calls))

        self.manager = self.remote.RemoteListenerManager(process_factory=factory)

    def tearDown(self):
        self.manager.shutdown()

    def test_http_and_sse_are_independent_and_token_never_enters_argv(self):
        preferences = _preferences()
        http = self.manager.start(preferences, "streamable-http")
        sse = self.manager.start(preferences, "sse")
        self.assertNotEqual(http["pid"], sse["pid"])
        self.assertIn("serve-remote", self.calls[0][0])
        self.assertNotIn(preferences.remote_token, self.calls[0][0])
        self.assertEqual(self.calls[0][1]["env"]["PARTME_BLENDER_REMOTE_TOKEN"], preferences.remote_token)
        self.manager.stop(preferences, "streamable-http")
        self.assertEqual(self.manager.snapshot(preferences, "streamable-http")["state"], "stopping")
        self.assertTrue(self.manager.snapshot(preferences, "sse")["running"])

    def test_public_address_uses_configured_https_base(self):
        preferences = _preferences(public_base_url="https://studio.example/base")
        self.assertEqual(
            self.manager.address(preferences, "streamable-http"),
            "https://studio.example/base/mcp",
        )

    def test_polling_a_stopped_listener_is_idempotent(self):
        preferences = _preferences()
        self.manager.start(preferences, "sse")
        self.manager.stop(preferences, "sse")
        self.assertIsNone(self.manager.poll(preferences))
        self.assertIsNone(self.manager.poll(preferences))
        self.assertEqual(self.manager.snapshot(preferences, "sse")["state"], "stopped")

    def test_missing_python_fails_before_spawning(self):
        with self.assertRaisesRegex(ValueError, "Python"):
            self.manager.start(_preferences(mcp_python="/missing/python"), "streamable-http")
        self.assertEqual(self.calls, [])

    def test_non_loopback_is_rejected_before_spawn_without_remote_security(self):
        preferences = _preferences(
            remote_host="0.0.0.0", remote_token="", issuer_url="", public_base_url="",
        )
        with self.assertRaisesRegex(ValueError, "Bearer Token"):
            self.manager.start(preferences, "streamable-http")
        self.assertEqual(self.calls, [])

        preferences.remote_token = "secret"
        preferences.issuer_url = "https://auth.example/"
        preferences.public_base_url = "http://studio.example"
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            self.manager.start(preferences, "streamable-http")
        self.assertEqual(self.calls, [])
        snapshot = self.manager.snapshot(preferences, "streamable-http")
        self.assertEqual(snapshot["state"], "configuration_required")
        self.assertIn("HTTPS", snapshot["message"])

    def test_stdio_missing_sdk_reports_recovery_instead_of_traceback(self):
        failure = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Traceback (most recent call last):\nModuleNotFoundError: No module named 'mcp'\n",
        )
        with patch.object(self.remote.subprocess, "run", return_value=failure):
            status = self.manager.probe_stdio(_preferences())

        self.assertEqual(status["state"], "unavailable")
        self.assertIn("官方 MCP SDK", status["message"])
        self.assertIn("MCP Python", status["message"])
        self.assertNotIn("Traceback", status["message"])

    def test_stdio_probe_allows_official_sdk_cold_start(self):
        ready = SimpleNamespace(returncode=0, stdout="ready\n", stderr="")
        with patch.object(self.remote.subprocess, "run", return_value=ready) as run:
            status = self.manager.probe_stdio(_preferences())

        self.assertEqual(status, {"state": "ready", "statusText": "已就绪", "message": ""})
        self.assertEqual(run.call_args.kwargs["timeout"], 8)


if __name__ == "__main__":
    unittest.main()
