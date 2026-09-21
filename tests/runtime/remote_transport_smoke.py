"""Real Blender smoke for the Access tab's stdio/HTTP/SSE lifecycle."""

import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


if "--" not in sys.argv:
    raise SystemExit("pass the extracted Add-on root after '--'")
addon_root = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
if not (addon_root / "partme_blender_mcp").is_dir():
    raise SystemExit("Add-on root does not contain partme_blender_mcp")
mcp_python = os.environ.get("PARTME_BLENDER_MCP_PYTHON")
if not mcp_python or not Path(mcp_python).is_file():
    raise SystemExit("PARTME_BLENDER_MCP_PYTHON must point to the installed release runtime")
sys.path.insert(0, str(addon_root))
tls_certfile = os.environ.get("PARTME_REMOTE_TLS_CERT", "")
tls_keyfile = os.environ.get("PARTME_REMOTE_TLS_KEY", "")
if bool(tls_certfile) != bool(tls_keyfile):
    raise SystemExit("PARTME_REMOTE_TLS_CERT and PARTME_REMOTE_TLS_KEY must be set together")
if tls_certfile and (not Path(tls_certfile).is_file() or not Path(tls_keyfile).is_file()):
    raise SystemExit("remote TLS certificate or key does not exist")

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


CATALOG_PROBE = '''
import hashlib
from mcp.types import PaginatedRequestParams
async def catalog_probe(session):
    cursor, pages, names, seen = None, 0, [], set()
    schemas = {}
    while True:
        page = await session.list_tools(params=PaginatedRequestParams(cursor=cursor))
        pages += 1
        for tool in page.tools:
            payload = tool.model_dump(by_alias=True)
            assert payload['name'] not in schemas, ('duplicate tool', payload['name'])
            assert payload['inputSchema'].get('type') == 'object', payload['name']
            names.append(payload['name'])
            schemas[payload['name']] = payload['inputSchema']
        cursor = page.model_dump(by_alias=True).get('nextCursor')
        if cursor is None:
            break
        assert cursor not in seen and pages < 100, 'pagination loop'
        seen.add(cursor)
    assert names and 'blender_connection_status' in names
    return {'toolCount': len(names), 'pages': pages,
            'schemaDigest': hashlib.sha256(json.dumps(schemas, sort_keys=True).encode()).hexdigest()}
'''


def client_process(transport, address, report_path, token, *, hold_seconds=2, ca_file=""):
    client_import = (
        "from mcp.client.streamable_http import streamable_http_client as connect"
        if transport == "streamable-http"
        else "from mcp.client.sse import sse_client as connect"
    )
    connect_args = (
        f"{address!r}, http_client=http_client"
        if transport == "streamable-http"
        else (f"{address!r}, headers={{'Authorization': 'Bearer ' + {token!r}}}, "
              "httpx_client_factory=client_factory")
    )
    source = f"""
import anyio, base64, json, ssl
from pathlib import Path
from mcp import ClientSession
{client_import}
try:
    import httpx2 as client_httpx
except ImportError:
    import httpx as client_httpx
{CATALOG_PROBE}
ssl_context = ssl.create_default_context(cafile={ca_file!r}) if {bool(ca_file)!r} else True
def client_factory(headers=None, timeout=None, auth=None):
    return client_httpx.AsyncClient(headers=headers, timeout=timeout, auth=auth, verify=ssl_context)
async def main():
    http_client = (client_httpx.AsyncClient(headers={{'Authorization': 'Bearer ' + {token!r}}},
                                            verify=ssl_context)
                   if {transport == 'streamable-http'!r} else None)
    async with connect({connect_args}) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            initialized = await session.initialize()
            result = await session.call_tool('blender_connection_status', {{}})
            catalog = await catalog_probe(session)
            visual = await session.call_tool('blender_scene_screenshot', {{
                'path': 'remote/{report_path.stem}.png', 'width': 32, 'height': 24,
                '_transactionId': 'remote-{report_path.stem}',
            }})
            initialized_payload = initialized.model_dump(by_alias=True)
            result_payload = result.model_dump(by_alias=True)
            visual_payload = visual.model_dump(by_alias=True)
            images = [block for block in visual_payload['content'] if block.get('type') == 'image']
            Path({str(report_path)!r}).write_text(json.dumps({{
                'server': initialized_payload['serverInfo']['name'],
                'isError': result_payload['isError'],
                'connected': result_payload['structuredContent'].get('connected'),
                'response': result_payload['structuredContent'],
                'catalog': catalog,
                'visual': {{
                    'isError': visual_payload['isError'],
                    'imageCount': len(images),
                    'mimeType': images[0]['mimeType'] if images else None,
                    'bytes': len(base64.b64decode(images[0]['data'])) if images else 0,
                }},
            }}))
            await anyio.sleep({hold_seconds!r})
anyio.run(main)
"""
    return subprocess.Popen([mcp_python, "-c", source], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def stdio_client_process(report_path, descriptor_path):
    """通过官方客户端验证公开 stdio，不将就绪探测当成协议验收。"""
    source = f"""
import anyio, base64, json, os
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
{CATALOG_PROBE}
async def main():
    env = dict(os.environ)
    env['PARTME_BLENDER_DESCRIPTOR'] = {str(descriptor_path)!r}
    env['PYTHONPATH'] = os.pathsep.join(filter(None, [
        {str(addon_root)!r}, env.get('PYTHONPATH'),
    ]))
    params = StdioServerParameters(command={mcp_python!r}, args=['-m', 'partme_blender_mcp'], env=env)
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            initialized = await session.initialize()
            result = await session.call_tool('blender_connection_status', {{}})
            catalog = await catalog_probe(session)
            visual = await session.call_tool('blender_scene_screenshot', {{
                'path': 'remote/{report_path.stem}.png', 'width': 32, 'height': 24,
                '_transactionId': 'remote-{report_path.stem}',
            }})
            initialized_payload = initialized.model_dump(by_alias=True)
            result_payload = result.model_dump(by_alias=True)
            visual_payload = visual.model_dump(by_alias=True)
            images = [block for block in visual_payload['content'] if block.get('type') == 'image']
            Path({str(report_path)!r}).write_text(json.dumps({{
                'server': initialized_payload['serverInfo']['name'],
                'isError': result_payload['isError'],
                'connected': result_payload['structuredContent'].get('connected'),
                'response': result_payload['structuredContent'],
                'catalog': catalog,
                'visual': {{
                    'isError': visual_payload['isError'],
                    'imageCount': len(images),
                    'mimeType': images[0]['mimeType'] if images else None,
                    'bytes': len(base64.b64decode(images[0]['data'])) if images else 0,
                }},
            }}))
anyio.run(main)
"""
    return subprocess.Popen([mcp_python, '-c', source], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


report = {"blender": bpy.app.version_string}
bpy.ops.preferences.addon_enable(module="partme_blender_mcp")
preferences = bpy.context.preferences.addons["partme_blender_mcp"].preferences
preferences.mcp_python = mcp_python
preferences.mcp_entrypoint = ""
preferences.remote_host = "127.0.0.1"
preferences.http_port = free_port()
preferences.sse_port = free_port()
preferences.remote_token = ""
preferences.tls_certfile = tls_certfile
preferences.tls_keyfile = tls_keyfile
report["tokenGenerate"] = list(bpy.ops.partme_blender.generate_remote_token())
token = preferences.remote_token
report["tokenConfigured"] = bool(token)
report["tokenShape"] = len(token) >= 43
report["tlsEnabled"] = bool(tls_certfile)

output_root = Path(tempfile.mkdtemp(prefix="pbm-remote-out-"))
bpy.context.scene.partme_blender_output_root = str(output_root)
report["startResult"] = list(bpy.ops.partme_blender.start_connector())
report["stdioRefresh"] = list(bpy.ops.partme_blender.refresh_access())

from partme_blender_mcp.remote import manager  # noqa: E402

stdio_status = manager().stdio_snapshot()
report["stdioState"] = stdio_status["state"]
report["stdioMessage"] = stdio_status.get("message", "")
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

# 不携带密钥/错误密钥都必须在协议处理之前被拒绝。
report['authRejections'] = {}
for transport, address in (('http', http_state['address']), ('sse', sse_state['address'])):
    for case, headers in (('missing', {}), ('invalid', {'Authorization': 'Bearer invalid-test-token'})):
        request = urllib.request.Request(address, headers=headers)
        try:
            context = ssl.create_default_context(cafile=tls_certfile) if tls_certfile else None
            with urllib.request.urlopen(request, timeout=3, context=context) as response:
                code = response.status
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
        report['authRejections'][transport + '_' + case] = code
        if code != 401:
            manager().shutdown()
            addon_runtime.stop()
            raise AssertionError(f'{transport} {case} token was not rejected: {code}')

temp_root = Path(tempfile.mkdtemp(prefix="pbm-remote-client-"))
http_report, http_report_2 = temp_root / "http.json", temp_root / "http-2.json"
sse_report = temp_root / "sse.json"
stdio_report = temp_root / 'stdio.json'
stdio_client = stdio_client_process(stdio_report, addon_runtime.current().descriptor_path)
http_client = client_process("streamable-http", http_state["address"], http_report, token,
                             hold_seconds=3, ca_file=tls_certfile)
http_client_2 = client_process("streamable-http", http_state["address"], http_report_2, token,
                               hold_seconds=3, ca_file=tls_certfile)
sse_client_process = client_process("sse", sse_state["address"], sse_report, token,
                                    hold_seconds=3, ca_file=tls_certfile)
def clients_finished_requests():
    for name, process in (("stdio", stdio_client), ("HTTP-1", http_client),
                          ("HTTP-2", http_client_2), ("SSE", sse_client_process)):
        if process.poll() is not None and process.returncode != 0:
            diagnostic = process.stderr.read().replace(token, "<redacted>")
            raise RuntimeError(f"{name} client exited {process.returncode}: {diagnostic}")
    return (stdio_report.is_file() and http_report.is_file()
            and http_report_2.is_file() and sse_report.is_file())


wait_for(clients_finished_requests)


def clients_visible():
    manager().poll(preferences)
    http_clients = manager().snapshot(preferences, "streamable-http")["clients"]
    sse_clients = manager().snapshot(preferences, "sse")["clients"]
    return (http_clients, sse_clients) if http_clients >= 2 and sse_clients >= 1 else None


report["activeClients"] = list(wait_for(clients_visible))

# 两个 HTTP 客户端正常离开后，监听器必须清理会话计数；随后第三个客户端可重连。
for process in (http_client, http_client_2):
    process.wait(timeout=8)


def http_clients_disconnected():
    manager().poll(preferences)
    clients = manager().snapshot(preferences, "streamable-http")["clients"]
    return True if clients == 0 else None


wait_for(http_clients_disconnected)
report["httpClientsAfterDisconnect"] = 0
reconnect_report = temp_root / "http-reconnect.json"
reconnect_client = client_process(
    "streamable-http", http_state["address"], reconnect_report, token,
    hold_seconds=5, ca_file=tls_certfile)


def reconnect_visible():
    if reconnect_client.poll() is not None and reconnect_client.returncode != 0:
        diagnostic = reconnect_client.stderr.read().replace(token, "<redacted>")
        raise RuntimeError(f"HTTP reconnect client exited {reconnect_client.returncode}: {diagnostic}")
    manager().poll(preferences)
    clients = manager().snapshot(preferences, "streamable-http")["clients"]
    return clients if reconnect_report.is_file() and clients >= 1 else None


report["httpReconnectClients"] = wait_for(reconnect_visible)
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

for process in (stdio_client, http_client, http_client_2, reconnect_client, sse_client_process):
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
    process.stdout.close()
    process.stderr.close()

report["httpClient"] = json.loads(http_report.read_text())
report["httpClient2"] = json.loads(http_report_2.read_text())
report["httpReconnectClient"] = json.loads(reconnect_report.read_text())
report["stdioClient"] = json.loads(stdio_report.read_text())
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
    "httpClientsAfterDisconnect": 0,
    "httpStoppedAlone": True,
    "sseStop": ["FINISHED"],
    "revokeResult": ["FINISHED"],
    "addonDisabled": True,
}
print("REMOTE_TRANSPORT_SMOKE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
for key, expected in required.items():
    if report.get(key) != expected:
        raise RuntimeError(f"remote transport smoke failed: {key}={report.get(key)!r}, expected {expected!r}")
for key in ("stdioClient", "httpClient", "httpClient2", "httpReconnectClient", "sseClient"):
    if {name: report[key][name] for name in ('server', 'isError', 'connected')} != {"server": "partme-blender-mcp", "isError": False, "connected": True}:
        raise RuntimeError(f"remote transport smoke failed: {key}={report[key]!r}")
    if report[key]["visual"]["isError"] or report[key]["visual"]["imageCount"] != 1:
        raise RuntimeError(f"remote visual content failed: {key}={report[key]['visual']!r}")
    if report[key]["visual"]["mimeType"] != "image/png" or report[key]["visual"]["bytes"] <= 0:
        raise RuntimeError(f"remote visual payload invalid: {key}={report[key]['visual']!r}")
assert report['stdioClient']['catalog'] == report['httpClient']['catalog'] == report['sseClient']['catalog']
assert report['httpClient2']['catalog'] == report['stdioClient']['catalog']
assert report['httpReconnectClient']['catalog'] == report['stdioClient']['catalog']
assert report['activeClients'][0] >= 2 and report['activeClients'][1] >= 1
assert report['httpReconnectClients'] >= 1
expected_scheme = 'https://' if report['tlsEnabled'] else 'http://'
assert report['httpAddress'].startswith(expected_scheme)
assert report['sseAddress'].startswith(expected_scheme)
