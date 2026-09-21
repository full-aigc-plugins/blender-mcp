"""Add-on and standalone Runtime must negotiate one immutable command contract."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from partme_blender_mcp.harness.mcp_adapter import (  # noqa: E402
    DescriptorBridge,
    McpAdapterError,
    discover_bridge,
)
from partme_blender_mcp.harness.runtime_contract import build_runtime_contract  # noqa: E402
from partme_blender_mcp.harness.version import __version__  # noqa: E402


class RuntimeContractHandshakeTests(unittest.TestCase):
    def _write_descriptor(self, folder: str, **overrides) -> Path:
        capabilities = [
            {"command": "scene.screenshot", "risk": "standard"},
            {"command": "session.status", "risk": "read"},
        ]
        descriptor = {
            "protocolVersion": "codex-blender/v1",
            "sessionId": "contract-test",
            "transport": "unix",
            "address": "/tmp/partme-contract-test.sock",
            "token": "private-token",
            "pid": os.getpid(),
            **build_runtime_contract(capabilities),
            **overrides,
        }
        path = Path(folder) / "contract-test.json"
        path.write_text(json.dumps(descriptor), encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def test_contract_is_order_independent_and_content_addressed(self):
        first = build_runtime_contract([
            {"command": "scene.screenshot", "risk": "standard"},
            {"command": "session.status", "risk": "read"},
        ])
        second = build_runtime_contract(list(reversed(first["capabilities"])))
        self.assertEqual(first, second)
        encoded = json.dumps(first["capabilities"], ensure_ascii=True,
                             separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.assertEqual(first["capabilitiesSha256"], hashlib.sha256(encoded).hexdigest())

    def test_legacy_descriptor_fails_with_actionable_version_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_descriptor(folder)
            descriptor = json.loads(path.read_text(encoding="utf-8"))
            for field in ("runtimeVersion", "harnessProtocolVersion", "capabilities", "capabilitiesSha256"):
                descriptor.pop(field)
            path.write_text(json.dumps(descriptor))
            os.chmod(path, 0o600)
            with self.assertRaises(McpAdapterError) as caught:
                DescriptorBridge(descriptor_path=path)._load()
        self.assertEqual(caught.exception.code, "ADDON_RUNTIME_VERSION_MISMATCH")

    def test_different_addon_version_fails_before_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_descriptor(folder, runtimeVersion="0.5.3")
            bridge = DescriptorBridge(descriptor_path=path, sender=lambda *_args, **_kwargs: self.fail("sent"))
            with self.assertRaises(McpAdapterError) as caught:
                bridge.call("scene.screenshot", {"path": "proof.png"})
        self.assertEqual(caught.exception.code, "ADDON_RUNTIME_VERSION_MISMATCH")
        self.assertIn(__version__, str(caught.exception))

    def test_discovery_preserves_single_version_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            self._write_descriptor(folder, runtimeVersion="0.5.3")
            with self.assertRaises(McpAdapterError) as caught:
                discover_bridge(Path(folder))
        self.assertEqual(caught.exception.code, "ADDON_RUNTIME_VERSION_MISMATCH")

    def test_tampered_capability_manifest_fails_before_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_descriptor(folder, capabilitiesSha256="0" * 64)
            bridge = DescriptorBridge(descriptor_path=path, sender=lambda *_args, **_kwargs: self.fail("sent"))
            with self.assertRaises(McpAdapterError) as caught:
                bridge.call("scene.screenshot", {"path": "proof.png"})
        self.assertEqual(caught.exception.code, "ADDON_RUNTIME_CAPABILITY_MISMATCH")

    def test_undeclared_command_fails_before_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = build_runtime_contract([
                {"command": "session.status", "risk": "read"},
            ])
            path = self._write_descriptor(folder, **contract)
            bridge = DescriptorBridge(descriptor_path=path, sender=lambda *_args, **_kwargs: self.fail("sent"))
            with self.assertRaises(McpAdapterError) as caught:
                bridge.call("scene.screenshot", {"path": "proof.png"})
        self.assertEqual(caught.exception.code, "ADDON_RUNTIME_CAPABILITY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
