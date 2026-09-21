"""PartMe Blender MCP adapter for the guarded Blender Harness."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from .runtime import build_registry
from .errors import HarnessError
from .image_artifact import MAX_IMAGE_BYTES, inspect_image_bytes
from .transport import Endpoint, send_request
from .version import (
    BLENDER_DOWNLOAD_URL,
    HARNESS_PROTOCOL_VERSION,
)
from .runtime_contract import RuntimeContractError, validate_runtime_contract
ENVELOPE_PROPERTIES = {
    "_requestId": {"type": "string", "minLength": 1, "description": "Stable request id for replay safety"},
    "_transactionId": {"type": "string", "minLength": 1, "description": "Harness milestone transaction id"},
    "_expectedSceneRevision": {"type": "integer", "minimum": 0},
    "_authorization": {"type": "string", "minLength": 1, "description": "Action-bound Harness authorization claim"},
}
CONTROL_TOOLS = {
    "blender_transaction_begin": "transaction.begin",
    "blender_transaction_commit": "transaction.commit",
    "blender_transaction_rollback": "transaction.rollback",
}
PUBLIC_EXCLUDED_COMMANDS = {"advanced.execute_python", "provider.task_control"}


class McpAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def command_tool_name(command: str) -> str:
    """Return a stable MCP-safe name which remains reversible by inspection."""
    return "blender_" + command.replace(".", "_")


def _static_registry():
    bpy_metadata = SimpleNamespace(
        app=SimpleNamespace(version=(5, 2, 1), background=False, version_string="catalog"),
    )
    # The public cross-client catalog excludes vendor-specific uploader commands.
    # Runtime availability and the Harness still decide whether a tool can execute.
    return build_registry(
        bpy_metadata,
        runtime_mode="managed",
        approved_output_root=Path(tempfile.gettempdir()) / "partme-blender-mcp-catalog",
    )


def _command_tool(registry, capability: dict) -> dict:
    command = capability["command"]
    detail = registry.describe_capability({"id": command})
    schema = deepcopy(detail["input"] or {"type": "object", "properties": {}, "additionalProperties": False})
    schema.setdefault("properties", {}).update(deepcopy(ENVELOPE_PROPERTIES))
    if capability["risk"] != "read":
        required = list(schema.get("required", []))
        if "_transactionId" not in required:
            required.append("_transactionId")
        schema["required"] = required
    schema["additionalProperties"] = False
    requirements = detail.get("context", {}).get("requirements", [])
    description = f"PartMe Blender Harness command `{command}`. Risk: {capability['risk']}; maturity: {detail['maturity']}."
    if capability["risk"] == "gated":
        description += (" Requires local user approval in Blender: a client cannot approve its own "
                        "request, and it retries the same request id after the user approves it.")
    if requirements:
        description += " Requirements: " + "; ".join(requirements)
    return {
        "name": command_tool_name(command),
        "title": command,
        "description": description,
        "inputSchema": schema,
        "outputSchema": {"type": "object"},
        "annotations": {
            "readOnlyHint": capability["risk"] == "read",
            "destructiveHint": capability["risk"] == "gated",
            "idempotentHint": capability["risk"] == "read",
            "openWorldHint": command.startswith("official_uploader."),
        },
        "_meta": {"codexBlenderCommand": command, "risk": capability["risk"], "maturity": detail["maturity"]},
    }


def build_tool_catalog(*, registry=None, plugin_root: Path | None = None) -> list[dict]:
    registry = registry or _static_registry()
    plugin_root = Path(plugin_root or Path(__file__).resolve().parents[2])
    tools = [
        {
            "name": "blender_getting_started",
            "title": "Install and connect Blender",
            "description": "Show the official Blender download and PartMe Blender MCP setup guide.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
        },
        {
            "name": "blender_connection_status",
            "title": "Blender MCP connection status",
            "description": "Check whether the plugin-owned MCP adapter can reach one live guarded Harness session.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
        },
    ]
    control_schema = {
        "type": "object",
        "properties": {
            "_requestId": deepcopy(ENVELOPE_PROPERTIES["_requestId"]),
            "_transactionId": deepcopy(ENVELOPE_PROPERTIES["_transactionId"]),
        },
        "required": ["_transactionId"],
        "additionalProperties": False,
    }
    for name, command in CONTROL_TOOLS.items():
        tools.append({
            "name": name, "title": command,
            "description": f"Guarded Harness lifecycle operation `{command}`.",
            "inputSchema": deepcopy(control_schema), "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": False, "destructiveHint": command == "transaction.rollback",
                            "idempotentHint": False, "openWorldHint": False},
            "_meta": {"codexBlenderControl": command},
        })
    command_tools = [
        _command_tool(registry, capability)
        for capability in registry.capabilities()
        if capability["command"] not in PUBLIC_EXCLUDED_COMMANDS
    ]
    all_names = [tool["name"] for tool in tools] + [tool["name"] for tool in command_tools]
    duplicates = sorted({name for name in all_names if all_names.count(name) > 1})
    if duplicates:
        raise McpAdapterError(
            "MCP_TOOL_NAME_COLLISION",
            "Harness command names do not map uniquely to MCP tools: " + ", ".join(duplicates),
        )
    tools.extend(command_tools)
    return tools


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _endpoint(descriptor: dict) -> Endpoint:
    address = descriptor["address"]
    if descriptor["transport"] == "tcp":
        address = (str(address[0]), int(address[1]))
    return Endpoint(str(descriptor["transport"]), address)


class DescriptorBridge:
    """Load one private Harness descriptor and forward closed requests."""

    def __init__(self, *, descriptor_path: Path, sender=send_request, process_alive=_process_alive):
        self.descriptor_path = Path(descriptor_path)
        self.sender = sender
        self.process_alive = process_alive

    def _load(self) -> dict:
        path = self.descriptor_path
        if path.is_symlink():
            raise McpAdapterError("UNSAFE_DESCRIPTOR", "Harness descriptor must not be a symlink")
        try:
            stat = path.stat()
        except FileNotFoundError as error:
            raise McpAdapterError("BLENDER_NOT_CONNECTED", "No active PartMe Blender Harness session") from error
        if os.name != "nt" and stat.st_mode & 0o077:
            raise McpAdapterError("UNSAFE_DESCRIPTOR", "Harness descriptor permissions are not private")
        try:
            descriptor = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise McpAdapterError("INVALID_DESCRIPTOR", "Harness descriptor is unreadable") from error
        required = {"protocolVersion", "sessionId", "transport", "address", "token", "pid"}
        if required.difference(descriptor) or descriptor.get("protocolVersion") != HARNESS_PROTOCOL_VERSION:
            raise McpAdapterError("INVALID_DESCRIPTOR", "Harness descriptor has an incompatible contract")
        try:
            validate_runtime_contract(descriptor)
        except RuntimeContractError as error:
            raise McpAdapterError(error.code, str(error)) from error
        if not self.process_alive(int(descriptor["pid"])):
            raise McpAdapterError("BLENDER_NOT_CONNECTED", "Harness process is no longer running")
        return descriptor

    def status(self) -> dict:
        descriptor = self._load()
        response = self.call("session.status", {}, request_id=str(uuid.uuid4()), transaction_id="mcp-status")
        if response.get("status") != "succeeded":
            raise McpAdapterError("BLENDER_NOT_CONNECTED", "Harness session did not answer its status probe")
        status = {
            "connected": True,
            "sessionId": descriptor["sessionId"],
            "transport": descriptor["transport"],
            "processId": descriptor["pid"],
            "sceneRevision": response.get("sceneRevision"),
            "runtimeVersion": descriptor["runtimeVersion"],
            "capabilityCount": len(descriptor["capabilities"]),
            "capabilitiesSha256": descriptor["capabilitiesSha256"],
        }
        if isinstance(response.get("result"), dict):
            status.update({key: value for key, value in response["result"].items()
                           if key not in {"token", "authorization"}})
        return status

    def authorized_output_root(self) -> Path:
        descriptor = self._load()
        value = descriptor.get("outputRoot")
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise McpAdapterError("INVALID_DESCRIPTOR", "Harness descriptor has no authorized output root")
        return Path(value).resolve()

    def call(self, command: str, arguments: dict, *, request_id: str | None = None,
             transaction_id: str | None = None, expected_scene_revision: int | None = None,
             authorization: str | None = None) -> dict:
        descriptor = self._load()
        supported = {item["command"] for item in descriptor["capabilities"]}
        if command not in supported:
            raise McpAdapterError(
                "ADDON_RUNTIME_CAPABILITY_MISMATCH",
                f"Blender Add-on {descriptor['runtimeVersion']} does not declare command {command}; reinstall the matching Add-on",
            )
        payload = {
            "protocolVersion": HARNESS_PROTOCOL_VERSION,
            "sessionId": descriptor["sessionId"],
            "requestId": request_id or str(uuid.uuid4()),
            "transactionId": transaction_id or "mcp-read",
            "command": command,
            "arguments": arguments,
        }
        if expected_scene_revision is not None:
            payload["expectedSceneRevision"] = expected_scene_revision
        if authorization is not None:
            payload["authorization"] = authorization
        try:
            return self.sender(_endpoint(descriptor), descriptor["token"], payload)
        except OSError as error:
            # 进程仍存活不代表旧 socket 有效；发现流程应跳过失效会话。
            raise McpAdapterError("BLENDER_NOT_CONNECTED", "Harness connection is unavailable") from error


def discover_bridge(runtime_dir: Path | None = None) -> DescriptorBridge:
    explicit = os.environ.get("PARTME_BLENDER_DESCRIPTOR") or os.environ.get("CODEX_BLENDER_DESCRIPTOR")
    if explicit:
        return DescriptorBridge(descriptor_path=Path(explicit))
    root = Path(runtime_dir or os.environ.get("PARTME_BLENDER_RUNTIME_DIR") or
                os.environ.get("CODEX_BLENDER_RUNTIME_DIR") or
                (Path(tempfile.gettempdir()) / "partme-blender"))
    live = []
    contract_errors = []
    for path in sorted(root.glob("*.json")) if root.is_dir() else []:
        bridge = DescriptorBridge(descriptor_path=path)
        try:
            bridge.status()
            live.append(bridge)
        except McpAdapterError as error:
            if error.code in {"ADDON_RUNTIME_VERSION_MISMATCH", "ADDON_RUNTIME_CAPABILITY_MISMATCH"}:
                contract_errors.append(error)
            continue
    if not live:
        if len(contract_errors) == 1:
            raise contract_errors[0]
        if contract_errors:
            raise McpAdapterError(
                "ADDON_RUNTIME_VERSION_MISMATCH",
                "Active Blender sessions use incompatible Add-on contracts; install the matching Add-on and restart Blender",
            )
        raise McpAdapterError("BLENDER_NOT_CONNECTED", "No active PartMe Blender Harness session")
    if len(live) != 1:
        raise McpAdapterError("AMBIGUOUS_SESSION", "Multiple Blender sessions are active; set PARTME_BLENDER_DESCRIPTOR")
    return live[0]


class McpAdapter:
    def __init__(self, *, bridge=None, plugin_root: Path | None = None, registry=None):
        self.plugin_root = Path(plugin_root or Path(__file__).resolve().parents[3]).resolve()
        self._bridge = bridge
        self.registry = registry or _static_registry()
        self.tools = build_tool_catalog(registry=self.registry, plugin_root=self.plugin_root)
        self.tools_by_name = {tool["name"]: tool for tool in self.tools}
        self.client: dict | None = None

    def record_client(self, client_info) -> None:
        """Remember the connecting client name/version for the local session record."""
        if not isinstance(client_info, dict):
            return
        name = client_info.get("name")
        version = client_info.get("version")
        self.client = {
            "name": name if isinstance(name, str) else "unknown",
            "version": version if isinstance(version, str) else "unknown",
        }

    def list_tools(self, *, cursor: str | None = None, limit: int = 50) -> dict:
        if cursor is None:
            offset = 0
        elif isinstance(cursor, str) and cursor.startswith("offset:") and cursor[7:].isdigit():
            offset = int(cursor[7:])
        else:
            raise McpAdapterError("INVALID_CURSOR", "tools/list cursor is invalid")
        if offset < 0 or offset > len(self.tools):
            raise McpAdapterError("INVALID_CURSOR", "tools/list cursor is out of range")
        page = self.tools[offset:offset + limit]
        result = {"tools": page}
        if offset + limit < len(self.tools):
            result["nextCursor"] = f"offset:{offset + limit}"
        return result

    def _active_bridge(self):
        return self._bridge or discover_bridge()

    def getting_started(self) -> dict:
        executable = shutil.which("blender")
        if executable is None and sys.platform == "darwin":
            candidate = Path("/Applications/Blender.app/Contents/MacOS/Blender")
            executable = str(candidate) if candidate.is_file() else None
        images = [
            ("Open Edit > Preferences", "docs/assets/reference/blender-open-preferences.png"),
            ("Install PartMe Blender MCP", "docs/assets/reference/blender-install-from-disk.png"),
        ]
        return {
            "blenderInstalled": executable is not None,
            "blenderExecutable": executable,
            "downloadUrl": BLENDER_DOWNLOAD_URL,
            "copy": {
                "zhCN": "还没有 Blender？下载安装包\n\n打开 Blender，在 偏好设置 > 插件 中启用 MCP 插件，然后在 N 面板中点击 Start MCP Server。",
                "en": "No Blender yet? Download the installer. Open Blender, enable the MCP Add-on in Preferences > Add-ons, then press N and click Start MCP Server.",
            },
            "addonName": "PartMe Blender MCP",
            "steps": [
                "Download Blender from the official Blender website and launch it once.",
                "Install partme-blender-mcp-addon-<version>.zip from Edit > Preferences > Add-ons > Install from Disk.",
                "Enable PartMe Blender MCP.",
                "In the 3D View press N, open PartMe MCP, choose approved output/assets, and click Start MCP Server.",
            ],
            "screenshots": [{"title": title, "path": str((self.plugin_root / relative).resolve())}
                            for title, relative in images],
        }

    @staticmethod
    def _result(payload: dict, *, is_error: bool = False, images: list[dict] | None = None) -> dict:
        content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}]
        content.extend(images or [])
        return {
            "content": content,
            "structuredContent": payload,
            "isError": is_error,
        }

    @staticmethod
    def _visual_content(command: str, response: dict, bridge) -> list[dict]:
        if command == "scene.screenshot":
            receipts = [response.get("result", {}).get("artifact")]
        elif command == "preview.capture":
            receipts = response.get("result", {}).get("milestone", {}).get("views", [])
        else:
            return []
        if not receipts or any(not isinstance(receipt, dict) for receipt in receipts):
            raise McpAdapterError("IMAGE_ARTIFACT_CHANGED", "visual result has no valid image receipt")
        root = Path(bridge.authorized_output_root()).resolve()
        images = []
        total = 0
        for receipt in receipts:
            path = Path(receipt.get("path", ""))
            try:
                resolved = path.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise McpAdapterError("IMAGE_ARTIFACT_CHANGED", "visual artifact is unavailable") from error
            if path.is_symlink() or not resolved.is_file() or not resolved.is_relative_to(root):
                raise McpAdapterError("IMAGE_ARTIFACT_CHANGED", "visual artifact is outside the authorized output root")
            size = resolved.stat().st_size
            if size <= 0 or size > MAX_IMAGE_BYTES:
                raise McpAdapterError("IMAGE_ARTIFACT_CHANGED", "visual response exceeds the 20 MiB limit")
            data = resolved.read_bytes()
            total += len(data)
            if len(data) != size or total > MAX_IMAGE_BYTES:
                raise McpAdapterError("IMAGE_ARTIFACT_CHANGED", "visual artifact changed while it was read")
            if hashlib.sha256(data).hexdigest() != receipt.get("sha256"):
                raise McpAdapterError("IMAGE_ARTIFACT_CHANGED", "visual artifact no longer matches its SHA-256")
            try:
                media_type, _, _ = inspect_image_bytes(data)
            except HarnessError as error:
                raise McpAdapterError("IMAGE_ARTIFACT_CHANGED", "visual artifact is not a supported image") from error
            images.append({"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": media_type})
        return images

    def _error(self, error: McpAdapterError) -> dict:
        payload = {"status": "failed", "error": {"code": error.code, "message": str(error)}}
        if error.code == "BLENDER_NOT_CONNECTED":
            payload["gettingStarted"] = self.getting_started()
        return self._result(payload, is_error=True)

    def call_tool(self, name: str, arguments: dict | None) -> dict:
        arguments = dict(arguments or {}) if isinstance(arguments or {}, dict) else None
        if arguments is None:
            return self._error(McpAdapterError("INVALID_ARGUMENT", "tool arguments must be an object"))
        if name == "blender_getting_started":
            if arguments:
                return self._error(McpAdapterError("INVALID_ARGUMENT", "getting started accepts no arguments"))
            return self._result(self.getting_started())
        if name == "blender_connection_status":
            if arguments:
                return self._error(McpAdapterError("INVALID_ARGUMENT", "connection status accepts no arguments"))
            try:
                payload = dict(self._active_bridge().status())
            except McpAdapterError as error:
                return self._error(error)
            payload["client"] = self.client or {"name": "unknown", "version": "unknown"}
            return self._result(payload)
        tool = self.tools_by_name.get(name)
        if tool is None:
            return self._error(McpAdapterError("UNKNOWN_TOOL", f"unknown MCP tool: {name}"))
        schema = tool["inputSchema"]
        unknown = sorted(set(arguments).difference(schema.get("properties", {})))
        missing = sorted(set(schema.get("required", [])).difference(arguments))
        if unknown or missing:
            detail = f"unknown fields: {unknown}" if unknown else f"missing fields: {missing}"
            return self._error(McpAdapterError("INVALID_ARGUMENT", detail))
        request_id = arguments.pop("_requestId", None)
        transaction_id = arguments.pop("_transactionId", None)
        expected_revision = arguments.pop("_expectedSceneRevision", None)
        authorization = arguments.pop("_authorization", None)
        command = tool.get("_meta", {}).get("codexBlenderCommand") or tool.get("_meta", {}).get("codexBlenderControl")
        try:
            bridge = self._active_bridge()
            risk = tool.get("_meta", {}).get("risk")
            if expected_revision is None and risk in {"standard", "gated"}:
                expected_revision = bridge.status().get("sceneRevision")
            response = bridge.call(
                command, arguments,
                request_id=request_id,
                transaction_id=transaction_id,
                expected_scene_revision=expected_revision,
                authorization=authorization,
            )
        except McpAdapterError as error:
            return self._error(error)
        failed = response.get("status") == "failed" or "error" in response
        if failed:
            return self._result(response, is_error=True)
        try:
            images = self._visual_content(command, response, bridge)
        except McpAdapterError as error:
            return self._error(error)
        return self._result(response, images=images)


def serve_stdio(input_stream=None, output_stream=None, adapter: McpAdapter | None = None) -> int:
    """Compatibility entry point backed exclusively by the official MCP SDK."""
    if input_stream is not None or output_stream is not None:
        raise ValueError("custom stdio streams are not supported by the official MCP SDK runner")
    from .sdk_server import serve_stdio as serve_sdk_stdio

    return serve_sdk_stdio(adapter or McpAdapter())


def main() -> int:
    """Console-script entry point."""
    return serve_stdio()
