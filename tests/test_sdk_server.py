"""Official MCP SDK bridge contracts."""

from __future__ import annotations

import importlib.util
import asyncio
import json
import tempfile
import unittest
from pathlib import Path


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
                    "content": [
                        {"type": "text", "text": '{"ok":true}'},
                        {"type": "image", "data": "iVBORw0KGgo=", "mimeType": "image/png"},
                    ],
                    "structuredContent": {"ok": True},
                    "isError": False,
                }

        adapter = Adapter()
        server = build_official_server(adapter)
        if hasattr(server, "get_request_handler"):
            page = await server.get_request_handler("tools/list").handler(
                object(), types.PaginatedRequestParams(cursor="offset:0")
            )
            result = await server.get_request_handler("tools/call").handler(
                object(), types.CallToolRequestParams(name="blender_probe", arguments={})
            )
        else:
            page = (await server.request_handlers[types.ListToolsRequest](
                types.ListToolsRequest(params=types.PaginatedRequestParams(cursor="offset:0"))
            )).root
            result = (await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(params=types.CallToolRequestParams(
                    name="blender_probe", arguments={}
                ))
            )).root
        page_payload = page.model_dump(by_alias=True)
        tool_payload = page_payload["tools"][0]
        self.assertEqual(page_payload["nextCursor"], "offset:50")
        self.assertEqual(tool_payload["inputSchema"]["additionalProperties"], False)
        self.assertTrue(tool_payload["annotations"]["readOnlyHint"])
        self.assertEqual(tool_payload["_meta"], {"risk": "read"})

        result_payload = result.model_dump(by_alias=True)
        self.assertEqual(result_payload["structuredContent"], {"ok": True})
        self.assertFalse(result_payload["isError"])
        self.assertEqual(result_payload["content"][1]["type"], "image")
        self.assertEqual(result_payload["content"][1]["mimeType"], "image/png")
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

    def test_streamable_http_app_uses_the_low_level_official_sdk(self):
        from partme_blender_mcp.harness.sdk_server import (
            RemoteServerConfig,
            build_remote_app,
        )

        class Adapter:
            def list_tools(self, *, cursor=None, limit=50):
                return {"tools": []}

            def call_tool(self, _name, _arguments):
                raise AssertionError("not called while constructing the app")

            def record_client(self, _client):
                pass

        app = build_remote_app(Adapter(), RemoteServerConfig(
            transport="streamable-http", host="127.0.0.1", port=9877,
        ))
        self.assertEqual(app.config.streamable_http_path, "/mcp")

    async def test_streamable_http_client_count_tracks_live_get_stream(self):
        from partme_blender_mcp.harness.sdk_server import ListenerStatusMiddleware, RemoteServerConfig

        entered = asyncio.Event()
        release = asyncio.Event()

        async def app(_scope, _receive, _send):
            entered.set()
            await release.wait()

        with tempfile.TemporaryDirectory() as directory:
            status_file = Path(directory) / "status.json"
            config = RemoteServerConfig(
                transport="streamable-http", host="127.0.0.1", port=9877,
                status_file=str(status_file),
            )
            middleware = ListenerStatusMiddleware(app, config)
            task = asyncio.create_task(middleware(
                {"type": "http", "method": "GET", "path": "/mcp", "headers": []},
                lambda: None, lambda _message: None,
            ))
            await entered.wait()
            self.assertEqual(json.loads(status_file.read_text(encoding="utf-8"))["clients"], 1)
            release.set()
            await task
            self.assertEqual(json.loads(status_file.read_text(encoding="utf-8"))["clients"], 0)


if __name__ == "__main__":
    unittest.main()
