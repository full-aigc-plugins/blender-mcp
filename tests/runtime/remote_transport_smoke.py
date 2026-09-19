"""Real Blender smoke for the Access tab's stdio/HTTP/SSE lifecycle."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


if "--" not in sys.argv:
    raise SystemExit("pass the extracted Add-on root after '--'")
addon_root = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
if not (addon_root / "partme_blender_mcp").is_dir():
    raise SystemExit("Add-on root does not contain partme_blender_mcp")
mcp_python = os.environ.get("PARTME_BLENDER_MCP_PYTHON")
if not mcp_python or not Path(mcp_python).is_file():
    raise SystemExit("PARTME_BLENDER_MCP_PYTHON must point to the installed 0.5.0 runtime")
sys.path.insert(0, str(addon_root))

import bpy  # noqa: E402
from partme_blender_mcp import runtime as addon_runtime  # noqa: E402


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_for(predicate, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        handle = addon_runtime.current()
        if handle is not None:
            handle.executor.pump()
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise RuntimeError("timed out waiting for remote transport state")


def client_process(transport, address, report_path, token):
    client_import = (
        "from mcp.client.streamable_http import streamable_http_client as connect"
        if transport == "streamable-http"
        else "from mcp.client.sse import sse_client as connect"
    )
    http_import = "import httpx2" if transport == "streamable-http" else ""
    connect_args = (
        f"{address!r}, http_client=http_client"
        if transport == "streamable-http"
        else f"{address!r}, headers={{'Authorization': 'Bearer ' + {token!r}}}"
    )
    source = f"""
import anyio, json
from pathlib import Path
from mcp import ClientSession
{client_import}
{http_import}
async def main():
    http_client = httpx2.AsyncClient(headers={{'Authorization': 'Bearer ' + {token!r}}}) if {transport == 'streamable-http'!r} else None
    async with connect({connect_args}) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            initialized = await session.initialize()
            result = await session.call_tool('blender_connection_status', {{}})
            Path({str(report_path)!r}).write_text(json.dumps({{
                'server': initialized.server_info.name,
                'isError': result.is_error,
                'connected': result.structured_content.get('connected'),
            }}))
            await anyio.sleep(2)
anyio.run(main)
"""
    return subprocess.Popen([mcp_python, "-c", source], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


report = {"blender": bpy.app.version_string}
bpy.ops.preferences.addon_enable(module="partme_blender_mcp")
preferences = bpy.context.preferences.addons["partme_blender_mcp"].preferences
preferences.mcp_python = mcp_python
preferences.mcp_entrypoint = ""
preferences.remote_host = "127.0.0.1"
preferences.http_port = free_port()
preferences.sse_port = free_port()
preferences.remote_token = ""
report["tokenGenerate"] = list(bpy.ops.partme_blender.generate_remote_token())
token = preferences.remote_token
report["tokenConfigured"] = bool(token)
report["tokenShape"] = len(token) >= 43

output_root = Path(tempfile.mkdtemp(prefix="pbm-remote-out-"))
bpy.context.scene.partme_blender_output_root = str(output_root)
report["startResult"] = list(bpy.ops.partme_blender.start_connector())
report["stdioRefresh"] = list(bpy.ops.partme_blender.refresh_access())

from partme_blender_mcp.remote import manager  # noqa: E402

report["stdioState"] = manager().stdio_snapshot()["state"]
report["httpStart"] = list(bpy.ops.partme_blender.toggle_remote(transport="streamable-http", enabled=True))
report["sseStart"] = list(bpy.ops.partme_blender.toggle_remote(transport="sse", enabled=True))


def both_running():
    manager().poll(preferences)
    http = manager().snapshot(preferences, "streamable-http")
    sse = manager().snapshot(preferences, "sse")
    return (http, sse) if http["state"] == sse["state"] == "running" else None


http_state, sse_state = wait_for(both_running)
report["httpAddress"] = http_state["address"]
report["sseAddress"] = sse_state["address"]

temp_root = Path(tempfile.mkdtemp(prefix="pbm-remote-client-"))
http_report, sse_report = temp_root / "http.json", temp_root / "sse.json"
http_client = client_process("streamable-http", http_state["address"], http_report, token)
sse_client_process = client_process("sse", sse_state["address"], sse_report, token)
wait_for(lambda: http_report.is_file() and sse_report.is_file())


def clients_visible():
    manager().poll(preferences)
    http_clients = manager().snapshot(preferences, "streamable-http")["clients"]
    sse_clients = manager().snapshot(preferences, "sse")["clients"]
    return (http_clients, sse_clients) if http_clients >= 1 and sse_clients >= 1 else None


report["activeClients"] = list(wait_for(clients_visible))
report["httpStop"] = list(bpy.ops.partme_blender.toggle_remote(transport="streamable-http", enabled=False))


def http_stopped_sse_running():
    manager().poll(preferences)
    http = manager().snapshot(preferences, "streamable-http")
    sse = manager().snapshot(preferences, "sse")
    return (http, sse) if http["state"] == "stopped" and sse["state"] == "running" else None


http_after, sse_after = wait_for(http_stopped_sse_running)
report["httpStoppedAlone"] = http_after["state"] == "stopped" and sse_after["state"] == "running"
report["sseStop"] = list(bpy.ops.partme_blender.toggle_remote(transport="sse", enabled=False))
wait_for(lambda: (manager().poll(preferences) is None
                  and manager().snapshot(preferences, "sse")["state"] == "stopped"))

for process in (http_client, sse_client_process):
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
    process.stdout.close()
    process.stderr.close()

report["httpClient"] = json.loads(http_report.read_text())
report["sseClient"] = json.loads(sse_report.read_text())
report["revokeResult"] = list(bpy.ops.partme_blender.revoke_connector())
bpy.ops.preferences.addon_disable(module="partme_blender_mcp")
report["addonDisabled"] = "partme_blender_mcp" not in bpy.context.preferences.addons

required = {
    "startResult": ["FINISHED"],
    "stdioRefresh": ["FINISHED"],
    "stdioState": "ready",
    "tokenGenerate": ["FINISHED"],
    "tokenConfigured": True,
    "tokenShape": True,
    "httpStart": ["FINISHED"],
    "sseStart": ["FINISHED"],
    "httpStoppedAlone": True,
    "sseStop": ["FINISHED"],
    "revokeResult": ["FINISHED"],
    "addonDisabled": True,
}
print("REMOTE_TRANSPORT_SMOKE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
for key, expected in required.items():
    if report.get(key) != expected:
        raise RuntimeError(f"remote transport smoke failed: {key}={report.get(key)!r}, expected {expected!r}")
for key in ("httpClient", "sseClient"):
    if report[key] != {"server": "partme-blender-mcp", "isError": False, "connected": True}:
        raise RuntimeError(f"remote transport smoke failed: {key}={report[key]!r}")
