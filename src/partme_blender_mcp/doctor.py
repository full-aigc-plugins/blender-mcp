"""Read-only environment diagnostics for PartMe Blender MCP."""

from __future__ import annotations

import json
import platform
import shutil
import sys
from pathlib import Path

from . import PRODUCT_NAME, __version__
from .harness.mcp_adapter import McpAdapterError, discover_bridge


def _blender_executable() -> str | None:
    found = shutil.which("blender")
    if found:
        return str(Path(found).resolve())
    candidates = []
    if sys.platform == "darwin":
        candidates.append(Path("/Applications/Blender.app/Contents/MacOS/Blender"))
    elif sys.platform == "win32":
        candidates.extend(Path("C:/Program Files/Blender Foundation").glob("Blender */blender.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def report() -> dict:
    executable = _blender_executable()
    try:
        connection = discover_bridge().status()
    except McpAdapterError as error:
        connection = {"connected": False, "error": {"code": error.code, "message": str(error)}}
    return {
        "product": PRODUCT_NAME,
        "version": __version__,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "supported": (3, 11) <= sys.version_info[:2] <= (3, 13),
        },
        "blenderInstalled": executable is not None,
        "blenderExecutable": executable,
        "connection": connection,
    }


def diagnose(*, as_json: bool = False) -> int:
    payload = report()
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{PRODUCT_NAME} {payload['version']}")
        print(f"Python: {payload['python']['version']} ({payload['python']['executable']})")
        print(f"Blender: {payload['blenderExecutable'] or 'not found'}")
        print(f"Connected: {payload['connection'].get('connected', False)}")
    return 0
