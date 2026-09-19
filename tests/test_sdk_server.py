"""Official MCP SDK bridge contracts."""

from __future__ import annotations

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("mcp"), "official MCP SDK is not installed in this test interpreter")
class OfficialSdkServerTests(unittest.IsolatedAsyncioTestCase):
    def _subject(self):
        from partme_blender_mcp.harness.sdk_server import (
            RemoteServerConfig,
            build_official_server,
            validate_remote_config,
        )

        return RemoteServerConfig, build_official_server, validate_remote_config

    async def test_catalog_and_results_are_adapted_without_losing_schema_or_pagination(self):
        from mcp import types

        _, build_official_server, _ = self._subject()

        class Adapter:
            def __init__(self):
                self.calls = []

            def list_tools(self, *, cursor=None, limit=50):
                self.calls.append(("list", cursor, limit))
                return {
                    "tools": [{
                        "name": "blender_probe",
                        "title": "Probe",
                        "description": "Probe Blender",
                        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                        "outputSchema": {"type": "object"},
                        "annotations": {"readOnlyHint": True, "openWorldHint": False},
                        "_meta": {"risk": "read"},
                    }],
                    "nextCursor": "offset:50",
                }

            def call_tool(self, name, arguments):
                self.calls.append(("call", name, arguments))
                return {
                    "content": [{"type": "text", "text": '{"ok":true}'}],
                    "structuredContent": {"ok": True},
                    "isError": False,
                }

        adapter = Adapter()
        server = build_official_server(adapter)
        page = await server.get_request_handler("tools/list").handler(
            object(), types.PaginatedRequestParams(cursor="offset:0")
        )
        self.assertEqual(page.next_cursor, "offset:50")
        self.assertEqual(page.tools[0].input_schema["additionalProperties"], False)
        self.assertTrue(page.tools[0].annotations.read_only_hint)
        self.assertEqual(page.tools[0].meta, {"risk": "read"})

        result = await server.get_request_handler("tools/call").handler(
            object(), types.CallToolRequestParams(name="blender_probe", arguments={})
        )
        self.assertEqual(result.structured_content, {"ok": True})
        self.assertFalse(result.is_error)
        self.assertEqual(adapter.calls[-1], ("call", "blender_probe", {}))

    def test_non_loopback_requires_authentication_and_https_public_url(self):
        RemoteServerConfig, _, validate_remote_config = self._subject()
        with self.assertRaisesRegex(ValueError, "bearer token"):
            validate_remote_config(RemoteServerConfig(transport="streamable-http", host="0.0.0.0", port=9877))
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_remote_config(RemoteServerConfig(
                transport="streamable-http", host="0.0.0.0", port=9877,
                token="secret", public_url="http://studio.lan:9877/mcp",
                issuer_url="https://auth.studio.lan/",
            ))
        config = RemoteServerConfig(
            transport="streamable-http", host="0.0.0.0", port=9877,
            token="secret", public_url="https://studio.example/mcp",
            issuer_url="https://auth.example/",
        )
        self.assertIs(validate_remote_config(config), config)

    def test_stdio_is_local_and_sse_has_separate_paths(self):
        RemoteServerConfig, _, validate_remote_config = self._subject()
        config = validate_remote_config(RemoteServerConfig(
            transport="sse", host="127.0.0.1", port=9878,
            sse_path="/events", message_path="/messages/",
        ))
        self.assertEqual(config.sse_path, "/events")
        self.assertEqual(config.message_path, "/messages/")


if __name__ == "__main__":
    unittest.main()
