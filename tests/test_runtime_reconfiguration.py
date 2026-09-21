"""Atomic execution-setting reconfiguration for a live Blender Harness."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from partme_blender_mcp.harness.errors import HarnessError  # noqa: E402
from partme_blender_mcp.harness.execution_policy import ExecutionPolicy  # noqa: E402
from partme_blender_mcp.harness.server import HarnessRuntime  # noqa: E402
from partme_blender_mcp.harness.session import HarnessSession  # noqa: E402


class RuntimeReconfigurationTests(unittest.TestCase):
    def setUp(self):
        self.old_dispatch = lambda _command, _arguments: {"result": "old"}
        self.new_dispatch = lambda _command, _arguments: {"result": "new"}
        self.session = HarnessSession(
            "session-1",
            dispatch=self.old_dispatch,
            execution_policy=ExecutionPolicy.interactive(),
        )

    def _runtime(self, descriptor_path, *, pending_count=0):
        return HarnessRuntime(
            endpoint=SimpleNamespace(kind="unix", address="/tmp/partme.sock"),
            descriptor_path=descriptor_path,
            transport=SimpleNamespace(close=lambda: None),
            executor=SimpleNamespace(pending_count=pending_count, cancel_pending=lambda: None),
            bpy_module=SimpleNamespace(),
            session=self.session,
        )

    def test_live_reconfigure_updates_dispatch_policy_and_descriptor_together(self):
        with tempfile.TemporaryDirectory() as folder:
            descriptor_path = Path(folder) / "session-1.json"
            descriptor_path.write_text(json.dumps({
                "protocolVersion": "codex-blender/v1",
                "sessionId": "session-1",
                "transport": "unix",
                "address": "/tmp/partme.sock",
                "token": "private-token",
                "pid": 123,
                "outputRoot": "/tmp/old-output",
                "assetRoots": ["/tmp/old-assets"],
                "executionPolicy": self.session.execution_policy.to_audit_dict(),
            }))
            runtime = self._runtime(descriptor_path)
            output_root = Path(folder) / "new-output"
            asset_root = Path(folder) / "new-assets"
            policy = ExecutionPolicy.from_dict({
                "mode": "auto_with_budget",
                "approvedOutputRoot": str(output_root),
                "allowDesignedProxies": True,
                "assetStrategy": "auto_search_generate",
            })
            registry = SimpleNamespace(
                dispatch=self.new_dispatch,
                capabilities=lambda: [{"command": "session.status", "risk": "read"}],
            )

            with patch("partme_blender_mcp.harness.runtime.build_registry", return_value=registry):
                result = runtime.reconfigure(
                    approved_output_root=output_root,
                    approved_asset_roots=[asset_root],
                    execution_policy=policy,
                    runtime_mode="connector",
                )

            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            self.assertIs(self.session.dispatch, self.new_dispatch)
            self.assertIs(self.session.execution_policy, policy)
            self.assertEqual(descriptor["token"], "private-token")
            self.assertEqual(descriptor["outputRoot"], str(output_root.resolve()))
            self.assertEqual(descriptor["assetRoots"], [str(asset_root.resolve())])
            self.assertEqual(descriptor["executionPolicy"], policy.to_audit_dict())
            self.assertEqual(result["outputRoot"], str(output_root.resolve()))
            self.assertEqual(result["assetRoots"], [str(asset_root.resolve())])

    def test_reconfigure_rejects_pending_commands_without_changing_state(self):
        with tempfile.TemporaryDirectory() as folder:
            descriptor_path = Path(folder) / "session-1.json"
            original = {"token": "private-token", "outputRoot": "/tmp/old-output"}
            descriptor_path.write_text(json.dumps(original))
            runtime = self._runtime(descriptor_path, pending_count=1)

            with self.assertRaisesRegex(HarnessError, "queued command"):
                runtime.reconfigure(
                    approved_output_root=Path(folder) / "new-output",
                    approved_asset_roots=[],
                    execution_policy=ExecutionPolicy.interactive(),
                    runtime_mode="connector",
                )

            self.assertIs(self.session.dispatch, self.old_dispatch)
            self.assertEqual(json.loads(descriptor_path.read_text(encoding="utf-8")), original)

    def test_reconfigure_rejects_active_transaction_and_pending_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            descriptor_path = Path(folder) / "session-1.json"
            descriptor_path.write_text(json.dumps({"token": "private-token"}))
            runtime = self._runtime(descriptor_path)
            self.session._active_transactions.add("tx-active")

            with self.assertRaisesRegex(HarnessError, "active transaction"):
                runtime.reconfigure(
                    approved_output_root=Path(folder) / "new-output",
                    approved_asset_roots=[],
                    execution_policy=ExecutionPolicy.interactive(),
                    runtime_mode="connector",
                )

            self.session._active_transactions.clear()
            self.session._pending_authorizations["r1"] = {
                "requestId": "r1", "command": "object.delete", "summary": "name=Cube",
                "requestedAt": 32503680000, "sceneRevision": 0,
            }
            with self.assertRaisesRegex(HarnessError, "pending approval"):
                runtime.reconfigure(
                    approved_output_root=Path(folder) / "new-output",
                    approved_asset_roots=[],
                    execution_policy=ExecutionPolicy.interactive(),
                    runtime_mode="connector",
                )

    def test_reconfigure_and_revoke_close_owned_dispatch_registry(self):
        class DispatchOwner:
            def __init__(self):
                self.closed = 0

            def dispatch(self, _command, _arguments):
                return {}

            def close(self):
                self.closed += 1

        old = DispatchOwner()
        replacement = DispatchOwner()
        session = HarnessSession("owned", dispatch=old.dispatch)
        session.apply_reconfiguration(
            dispatch=replacement.dispatch,
            execution_policy=ExecutionPolicy.interactive(),
        )
        self.assertEqual(old.closed, 1)
        self.assertEqual(replacement.closed, 0)
        session.revoke()
        self.assertEqual(replacement.closed, 1)


if __name__ == "__main__":
    unittest.main()
