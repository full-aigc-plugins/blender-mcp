"""Generic MCP client handshake against a live Blender Harness.

Run inside Blender, never against a user's open project:

    BLENDER_USER_CONFIG=/tmp/pbm-config BLENDER_USER_SCRIPTS=/tmp/pbm-addons \\
      /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \\
      --python-exit-code 1 --python tests/runtime/generic_mcp_client_handshake.py \\
      -- /tmp/addon-extract/partme_blender_mcp

The second argument (after ``--``) is a directory that contains ``partme_blender_mcp``
exactly as a user installs it, so the shipped layout is what gets exercised.

This is a host-neutral conformance run: a subprocess speaks JSON-RPC over stdio to
``python -m partme_blender_mcp``, exactly like Claude Desktop, Claude Code, Cursor,
MiniMax Design, or any other MCP client. It covers initialize, the initialized
notification, paginated tools/list, tools/call for a read and for a transaction-backed
write, and the local approval handshake for a gated command.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import bpy  # noqa: E402

from partme_blender_mcp.harness.server import start_harness  # noqa: E402


def _addon_root(argv):
    if "--" not in argv:
        raise SystemExit("pass the installed add-on directory after '--'")
    candidate = Path(argv[argv.index("--") + 1]).resolve()
    if not (candidate / "partme_blender_mcp").is_dir():
        raise SystemExit(f"{candidate} does not contain partme_blender_mcp/")
    return candidate


class McpClient:
    """Minimal line-delimited JSON-RPC client for the MCP stdio transport."""

    def __init__(self, runtime_dir: Path, addon_root: Path):
        env = dict(os.environ)
        env["PARTME_BLENDER_RUNTIME_DIR"] = str(runtime_dir)
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(addon_root), str(Path(__file__).resolve().parents[2] / "src"), env.get("PYTHONPATH")])
        )
        self.process = subprocess.Popen(
            [sys.executable, "-m", "partme_blender_mcp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, cwd=str(addon_root),
        )
        self.next_id = 0

    def request(self, method, params=None):
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            message["params"] = params
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"server closed the stream during {method}: {self.process.stderr.read()}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(f"{method} failed: {response['error']}")
        return response["result"]

    def notify(self, method, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def call_tool(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        self.process.stdin.close()
        return self.process.wait(timeout=30)


def _payload(result):
    """Structured content when present, else the decoded text block."""
    if "structuredContent" in result:
        return result["structuredContent"]
    return json.loads(result["content"][0]["text"])


def _scene_objects(client):
    """The inspected object names, taken from the harness response's result payload."""
    response = _payload(client.call_tool("blender_scene_inspect", {}))
    return response.get("result", {}).get("objects", [])


def run_client(runtime_dir: Path, addon_root: Path, report: dict, approval_gate: threading.Event,
               approval_box: dict, approval_done: threading.Event):
    client = McpClient(runtime_dir, addon_root)
    try:
        # 1. initialize: the client declares its identity and protocol version.
        initial = client.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "generic-handshake-probe", "version": "1.0"},
        })
        report["protocolVersion"] = initial["protocolVersion"]
        report["serverInfo"] = initial["serverInfo"]
        report["serverCapabilities"] = sorted(initial["capabilities"])

        # 2. notifications/initialized carries no id and produces no response.
        client.notify("notifications/initialized")

        # 3. tools/list must be followed through every page via nextCursor.
        names, cursor, pages = [], None, 0
        while True:
            page = client.request("tools/list", {"cursor": cursor} if cursor else {})
            pages += 1
            names.extend(tool["name"] for tool in page["tools"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        report["toolPages"] = pages
        report["toolCount"] = len(names)
        report["doubleUnderscoreNames"] = [name for name in names if "__" in name][:5]

        # 4. read-only smoke: exactly what the guides tell a user to run first.
        status = _payload(client.call_tool("blender_connection_status", {}))
        report["connectionStatus"] = {
            "connected": status.get("connected"),
            "sessionId": status.get("sessionId"),
            "client": status.get("client"),
        }
        report["sceneObjectsBefore"] = _scene_objects(client)

        # 5. a transaction-backed write through the Harness.
        begin = _payload(client.call_tool("blender_transaction_begin", {"_transactionId": "tx-handshake"}))
        report["transactionBegin"] = begin.get("status")
        created = client.call_tool("blender_object_create_mesh", {
            "name": "HandshakeProbe", "primitive": "cube",
            "_requestId": "create-1", "_transactionId": "tx-handshake",
        })
        report["createIsError"] = created.get("isError", False)
        report["createChangedObjects"] = _payload(created).get("changedObjects")
        committed = _payload(client.call_tool("blender_transaction_commit", {"_transactionId": "tx-handshake"}))
        report["transactionCommit"] = committed.get("status")
        report["probePresentAfterCreate"] = "HandshakeProbe" in _scene_objects(client)

        # 6. a gated command must be refused: no client can approve itself.
        begin = _payload(client.call_tool("blender_transaction_begin", {"_transactionId": "tx-gated"}))
        report["gatedTransactionBegin"] = begin.get("status")
        denied = client.call_tool("blender_object_delete", {
            "name": "HandshakeProbe",
            "_requestId": "gated-1", "_transactionId": "tx-gated",
        })
        denied_payload = _payload(denied)
        report["gatedIsError"] = denied.get("isError", False)
        report["gatedErrorCode"] = denied_payload.get("error", {}).get("code")
        report["probePresentAfterRefusal"] = "HandshakeProbe" in _scene_objects(client)

        # 7. the Blender-side user approves this exact request id.
        approval_box["requestId"] = "gated-1"
        approval_gate.set()
        if not approval_done.wait(timeout=60):
            raise RuntimeError("host never approved the pending request")

        # 8. the client retries the same request id and is allowed exactly once.
        retried = client.call_tool("blender_object_delete", {
            "name": "HandshakeProbe",
            "_requestId": "gated-1", "_transactionId": "tx-gated",
        })
        retried_payload = _payload(retried)
        report["gatedRetryIsError"] = retried.get("isError", False)
        report["gatedRetryStatus"] = retried_payload.get("status")
        report["gatedRetryErrorCode"] = retried_payload.get("error", {}).get("code")
        report["probePresentAfterDelete"] = "HandshakeProbe" in _scene_objects(client)
        report["transactionRollback"] = _payload(
            client.call_tool("blender_transaction_rollback", {"_transactionId": "tx-gated"})
        ).get("status")
        report["probePresentAfterRollback"] = "HandshakeProbe" in _scene_objects(client)
        report["sessionPendingAuthorizations"] = _payload(
            client.call_tool("blender_connection_status", {})
        ).get("pendingAuthorizations")

        # 9. closing stdin ends the server cleanly.
        report["clientExitCode"] = client.close()
    except Exception as exc:  # keep the host-side report complete
        report["clientError"] = repr(exc)
        report["clientStderr"] = client.process.stderr.read()[-2000:]
        client.process.kill()


def _short_runtime_dir() -> Path:
    """Keep the runtime directory short: a Unix socket name must fit sun_path (104 bytes)."""
    base = "/tmp" if Path("/tmp").is_dir() else None
    return Path(tempfile.mkdtemp(prefix="pbm-hs-", dir=base))


def main():
    addon_root = _addon_root(sys.argv)
    runtime_dir = _short_runtime_dir()
    output_root = runtime_dir / "outputs"
    output_root.mkdir(parents=True)
    runtime = start_harness(
        bpy, session_id="handshake", runtime_dir=runtime_dir,
        approved_output_root=output_root, show_frontend=False,
    )
    report = {"blender": bpy.app.version_string, "runtimeDir": str(runtime_dir)}
    approval_gate, approval_done, approval_box = threading.Event(), threading.Event(), {}

    thread = threading.Thread(
        target=run_client,
        args=(runtime_dir, addon_root, report, approval_gate, approval_box, approval_done),
        daemon=True,
    )
    thread.start()
    try:
        while thread.is_alive():
            # Blender's main thread owns command execution; drive the queue while the
            # external client waits on the socket.
            runtime.executor.pump()
            if approval_gate.is_set() and not approval_done.is_set():
                approved = runtime.session.approve_pending(approval_box["requestId"])
                report["hostApproved"] = approved
                approval_done.set()
            time.sleep(0.01)
    finally:
        thread.join(timeout=10)
        runtime.executor.pump()
        runtime.close()
    print("HANDSHAKE=" + json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
