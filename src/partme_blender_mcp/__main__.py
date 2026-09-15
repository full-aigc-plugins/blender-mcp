"""Run the PartMe Blender MCP stdio server or read-only diagnostics."""

from __future__ import annotations

import argparse

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
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return diagnose(as_json=args.as_json)
    return serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
