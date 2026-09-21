"""失效连接必须转成 MCP 领域错误，不能泄漏 socket 异常。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from partme_blender_mcp.harness.mcp_adapter import DescriptorBridge, McpAdapterError  # noqa: E402


class BridgeDisconnectTests(unittest.TestCase):
    def test_refused_socket_is_reported_as_disconnected(self):
        bridge = DescriptorBridge(descriptor_path="unused")
        descriptor = {
            "sessionId": "test", "transport": "unix", "address": "/tmp/missing.sock", "token": "secret",
            "runtimeVersion": "test", "capabilities": [{"command": "session.status", "risk": "read"}],
        }
        with patch.object(bridge, "_load", return_value=descriptor), patch.object(
            bridge, "sender", side_effect=ConnectionRefusedError("sensitive endpoint")
        ):
            with self.assertRaises(McpAdapterError) as caught:
                bridge.call("session.status", {})
        self.assertEqual(caught.exception.code, "BLENDER_NOT_CONNECTED")
        self.assertNotIn("sensitive", str(caught.exception))
