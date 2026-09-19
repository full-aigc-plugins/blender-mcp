"""Run the PartMe Blender MCP stdio server or read-only diagnostics."""

from __future__ import annotations

import argparse
import os

from .doctor import diagnose
from .harness.mcp_adapter import serve_stdio
from .harness.version import PRODUCT_NAME, __version__


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="partme-blender-mcp",
        description="Secure cross-client Blender MCP runtime",
        epilog="Read-only diagnostic: partme-blender-mcp doctor --json",
    )
    parser.add_argument("--version", action="version", version=f"{PRODUCT_NAME} {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    doctor = subparsers.add_parser("doctor", help="inspect local Blender and Harness state")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    remote = subparsers.add_parser("serve-remote", help="run one official SDK HTTP or SSE listener")
    remote.add_argument("transport", choices=("streamable-http", "sse"))
    remote.add_argument("--host", default="127.0.0.1")
    remote.add_argument("--port", type=int, required=True)
    remote.add_argument("--public-url")
    remote.add_argument("--issuer-url")
    remote.add_argument("--streamable-http-path", default="/mcp")
    remote.add_argument("--sse-path", default="/sse")
    remote.add_argument("--message-path", default="/messages/")
    remote.add_argument("--allowed-host", action="append", default=[])
    remote.add_argument("--allowed-origin", action="append", default=[])
    remote.add_argument("--tls-certfile")
    remote.add_argument("--tls-keyfile")
    remote.add_argument("--status-file")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return diagnose(as_json=args.as_json)
    if args.command == "serve-remote":
        from .harness.mcp_adapter import McpAdapter
        from .harness.sdk_server import RemoteServerConfig, serve_remote

        return serve_remote(McpAdapter(), RemoteServerConfig(
            transport=args.transport,
            host=args.host,
            port=args.port,
            streamable_http_path=args.streamable_http_path,
            sse_path=args.sse_path,
            message_path=args.message_path,
            token=os.environ.get("PARTME_BLENDER_REMOTE_TOKEN"),
            public_url=args.public_url,
            issuer_url=args.issuer_url,
            allowed_hosts=tuple(args.allowed_host),
            allowed_origins=tuple(args.allowed_origin),
            tls_certfile=args.tls_certfile,
            tls_keyfile=args.tls_keyfile,
            status_file=args.status_file,
        ))
    return serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
