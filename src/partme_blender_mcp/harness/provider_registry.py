"""Provider catalog and secret-free status protocol shared by Blender surfaces."""

from __future__ import annotations

import importlib
import json
import os
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .provider_tasks import ProviderTaskRegistry, get_provider_task_registry


PROVIDER_STATUS_SCHEMA = "partme-provider-status/v1"
PROVIDER_CATALOG_SCHEMA = "partme-provider-catalog/v1"
VALID_CATEGORIES = {"asset_library", "ai_model"}
VALID_SOURCES = {"native", "community"}
VALID_STATES = {"ready", "disabled", "configuration_required", "unavailable", "busy", "error"}
VALID_RISKS = {"read", "network_download", "paid_generation", "scene_import", "external_export"}
ACTIVE_TASK_STATUS = {
    "submitting": "提交中",
    "querying": "查询中",
    "generating": "生成中",
    "downloading": "下载中",
    "staged": "等待导入",
    "importing": "导入中",
}
SECRET_KEY = re.compile(r"(?:api.?key|token|secret|password|credential)", re.IGNORECASE)
STATUS_COMMAND = re.compile(r"get_[a-z0-9_]+_status")


class ProviderRegistryError(ValueError):
    """The provider contribution is malformed or unsafe to expose."""


def _contains_secret(value, key="") -> bool:
    if SECRET_KEY.search(str(key)):
        return True
    if isinstance(value, dict):
        return any(_contains_secret(child, child_key) for child_key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(child) for child in value)
    return False


@dataclass(frozen=True)
class ProviderDefinition:
    provider_id: str
    label: str
    category: str
    source: str
    risks: tuple[str, ...]
    status: dict = field(default_factory=lambda: {"state": "unavailable", "statusText": "不可用"})
    actions: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)
    enabled: bool = True
    mutable: bool = True
    configurable: bool = False
    status_probe: Callable[[object | None], dict] | None = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.provider_id):
            raise ProviderRegistryError("providerId must be lower snake_case")
        if not self.label:
            raise ProviderRegistryError("provider label is required")
        if self.category not in VALID_CATEGORIES:
            raise ProviderRegistryError(f"unknown provider category: {self.category}")
        if self.source not in VALID_SOURCES:
            raise ProviderRegistryError(f"unknown provider source: {self.source}")
        if not self.risks or set(self.risks) - VALID_RISKS:
            raise ProviderRegistryError("provider risks are empty or invalid")
        if self.status.get("state") not in VALID_STATES:
            raise ProviderRegistryError("provider status state is invalid")
        if type(self.enabled) is not bool or type(self.mutable) is not bool or type(self.configurable) is not bool:
            raise ProviderRegistryError("provider enabled, mutable and configurable flags must be booleans")
        if _contains_secret(self.metadata):
            raise ProviderRegistryError("provider metadata must not contain credentials")


class ProviderRegistry:
    def __init__(self, *, task_registry: ProviderTaskRegistry | None = None):
        self._providers: dict[str, ProviderDefinition] = {}
        self._status_overrides: dict[str, dict] = {}
        self._enabled_overrides: dict[str, bool] = {}
        self._task_registry = task_registry or get_provider_task_registry()

    def clear(self) -> None:
        self._providers.clear()
        self._status_overrides.clear()
        self._enabled_overrides.clear()

    def register(self, definition: ProviderDefinition) -> None:
        if definition.provider_id in self._providers:
            raise ProviderRegistryError(f"provider already registered: {definition.provider_id}")
        self._providers[definition.provider_id] = definition

    def load(self, path: Path) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != PROVIDER_CATALOG_SCHEMA or not isinstance(payload.get("providers"), list):
            raise ProviderRegistryError("provider catalog schema is invalid")
        for item in payload["providers"]:
            allowed = {
                "providerId", "label", "category", "source", "risks", "status", "actions", "metadata",
                "enabled", "mutable", "configurable",
            }
            if not isinstance(item, dict) or set(item) - allowed:
                raise ProviderRegistryError("provider contribution contains unknown fields")
            metadata = dict(item.get("metadata") or {})
            status_probe = None
            if item.get("providerId") in {"polyhaven", "sketchfab", "hyper3d", "hunyuan3d"}:
                # 凭证和路由偏好由 PartMe 所有，不再要求另装社区 Add-on。
                metadata.pop("enableProperty", None)
                metadata.pop("preferencesModule", None)
                status_probe = _partme_provider_status(item["providerId"])
            elif item.get("source") == "community" and metadata.get("statusCommand"):
                status_probe = _community_status_probe(metadata["statusCommand"], metadata)
            self.register(ProviderDefinition(
                provider_id=item.get("providerId", ""),
                label=item.get("label", ""),
                category=item.get("category", ""),
                source=item.get("source", ""),
                risks=tuple(item.get("risks", ())),
                status=dict(item.get("status") or {"state": "unavailable", "statusText": "不可用"}),
                actions=tuple(item.get("actions", ())),
                metadata=metadata,
                enabled=item.get("enabled", True),
                mutable=item.get("mutable", True),
                configurable=item.get("configurable", "configure" in item.get("actions", ())),
                status_probe=status_probe,
            ))

    def _enabled(self, definition: ProviderDefinition, context=None) -> bool:
        override = self._enabled_overrides.get(definition.provider_id)
        if override is not None:
            return override
        property_name = definition.metadata.get("enableProperty")
        scene = getattr(context, "scene", None)
        if isinstance(property_name, str) and scene is not None and hasattr(scene, property_name):
            return bool(getattr(scene, property_name))
        return definition.enabled

    def _base_status(self, definition: ProviderDefinition) -> dict:
        status = dict(definition.status)
        status.update(self._status_overrides.get(definition.provider_id, {}))
        if status.get("state") not in VALID_STATES:
            return {"state": "error", "statusText": "状态协议错误"}
        return status

    def snapshot(self, context=None) -> dict:
        rows = []
        for definition in self._providers.values():
            status = self._base_status(definition)
            preferred_enabled = self._enabled(definition, context)
            enabled = preferred_enabled and status["state"] != "configuration_required"
            actions = list(definition.actions)
            task = self._task_registry.latest(definition.provider_id)
            active = task is not None and task["active"]
            if active:
                status = {
                    "state": "busy",
                    "statusText": task.get("statusText") or ACTIVE_TASK_STATUS.get(task["state"], "处理中"),
                }
                if "cancel" not in actions:
                    actions.append("cancel")
            elif not enabled and status["state"] != "configuration_required":
                status = {"state": "disabled", "statusText": "已关闭"}
            row = {
                "schemaVersion": PROVIDER_STATUS_SCHEMA,
                "providerId": definition.provider_id,
                "label": definition.label,
                "category": definition.category,
                "source": definition.source,
                "enabled": enabled,
                "defaultEnabled": definition.enabled,
                "mutable": definition.mutable,
                "configurable": definition.configurable,
                # A temporary provider outage must not erase or prevent the user's
                # routing preference. Missing required configuration is different: the
                # configuration action must succeed before a disabled provider can start.
                "toggleLocked": (
                    not definition.mutable or active or
                    status["state"] == "configuration_required"
                ),
                "state": status["state"],
                "statusText": str(status.get("statusText") or status["state"]),
                "risks": list(definition.risks),
                "actions": actions,
                "metadata": dict(definition.metadata),
            }
            if task is not None:
                row["task"] = task
            rows.append(row)
        return {
            "schemaVersion": PROVIDER_STATUS_SCHEMA,
            "providers": rows,
            "summary": {
                "ready": sum(row["enabled"] and row["state"] == "ready" for row in rows),
                "total": len(rows),
                "busy": sum(row["enabled"] and row["state"] == "busy" for row in rows),
                "available": sum(row["enabled"] and row["state"] in {"ready", "busy"} for row in rows),
            },
        }

    def refresh(self, context=None) -> dict:
        """Probe providers once and cache results so Blender draw calls never perform I/O."""
        for definition in self._providers.values():
            if definition.status_probe is None:
                continue
            try:
                status = definition.status_probe(context)
                if not isinstance(status, dict) or status.get("state") not in VALID_STATES:
                    raise ProviderRegistryError("status probe returned an invalid state")
                self._status_overrides[definition.provider_id] = dict(status)
            except Exception:
                self._status_overrides[definition.provider_id] = {
                    "state": "error", "statusText": "状态检查失败",
                }
        return self.snapshot(context)

    def set_status(self, provider_id: str, status: dict) -> None:
        if provider_id not in self._providers:
            raise ProviderRegistryError(f"unknown provider: {provider_id}")
        if not isinstance(status, dict) or status.get("state") not in VALID_STATES:
            raise ProviderRegistryError("provider status state is invalid")
        self._status_overrides[provider_id] = dict(status)

    def set_enabled(self, provider_id: str, enabled: bool, *, context=None) -> dict:
        if type(enabled) is not bool:
            raise ProviderRegistryError("provider enabled value must be boolean")
        definition = self._providers.get(provider_id)
        if definition is None:
            raise ProviderRegistryError(f"unknown provider: {provider_id}")
        if not definition.mutable:
            raise ProviderRegistryError(f"provider cannot be disabled: {provider_id}")
        task = self._task_registry.latest(provider_id, active_only=True)
        if task is not None:
            raise ProviderRegistryError(f"provider has an active task: {provider_id}")
        if enabled and self._base_status(definition)["state"] == "configuration_required":
            raise ProviderRegistryError(f"provider requires configuration: {provider_id}")
        property_name = definition.metadata.get("enableProperty")
        if isinstance(property_name, str):
            scene = getattr(context, "scene", None)
            if scene is None or not hasattr(scene, property_name):
                raise ProviderRegistryError(f"provider runtime property is unavailable: {provider_id}")
            setattr(scene, property_name, enabled)
        self._enabled_overrides[provider_id] = enabled
        return next(row for row in self.snapshot(context)["providers"] if row["providerId"] == provider_id)

    def require_enabled(self, provider_id: str, *, context=None) -> None:
        """Reject routing to a registered provider that the user disabled or cannot configure."""
        definition = self._providers.get(provider_id)
        if definition is None:
            return
        if not self._enabled(definition, context):
            raise ProviderRegistryError(f"provider is disabled: {provider_id}")
        status = self._base_status(definition)
        if status["state"] == "configuration_required":
            raise ProviderRegistryError(f"provider requires configuration: {provider_id}")
        if status["state"] in {"unavailable", "error"}:
            raise ProviderRegistryError(f"provider is unavailable: {provider_id}")


def _asset_root_status(context) -> dict:
    scene = getattr(context, "scene", None)
    root = getattr(scene, "partme_blender_asset_root", "") if scene is not None else ""
    return ({"state": "ready", "statusText": "PartMe 原生"} if root else
            {"state": "configuration_required", "statusText": "需要素材目录"})


def _polypizza_status(_context) -> dict:
    return ({"state": "ready", "statusText": "PartMe 原生"} if os.environ.get("POLYPIZZA_API_KEY") else
            {"state": "configuration_required", "statusText": "需要 API Key"})


def _community_status(result: dict, *, ready_text: str = "已配置") -> dict:
    if result.get("error"):
        return {"state": "error", "statusText": "状态检查失败"}
    if result.get("enabled") is True:
        return {"state": "ready", "statusText": ready_text}
    message = str(result.get("message") or "").lower()
    needs_configuration = any(token in message for token in (
        "api key", "api url", "secretid", "secretkey", "not given", "invalid",
    ))
    return {
        "state": "configuration_required" if needs_configuration else "disabled",
        "statusText": "需要配置" if needs_configuration else "未启用",
    }


def _in_process_community_status(command: str, metadata: dict, context) -> dict | None:
    """Read the community add-on on Blender's main thread without a socket round trip.

    The community bridge services its socket queue on Blender's main thread. Calling
    that socket from another panel operator on the same thread deadlocks until timeout.
    A direct status read also keeps credentials inside Blender.
    """
    if context is None or not metadata.get("preferencesModule"):
        return None
    try:
        bpy = importlib.import_module("bpy")
    except (ImportError, ModuleNotFoundError):
        return None
    server = getattr(getattr(bpy, "types", None), "blendermcp_server", None)
    if server is None:
        return None
    scene = getattr(context, "scene", None)
    enabled = bool(getattr(scene, metadata.get("enableProperty", ""), False))

    if command == "get_sketchfab_status":
        key_reader = getattr(server, "_get_sketchfab_api_key", None)
        if not callable(key_reader) or not key_reader():
            return {"state": "configuration_required", "statusText": "需要配置"}
        return ({"state": "ready", "statusText": "已配置"} if enabled else
                {"state": "disabled", "statusText": "未启用"})

    if command == "get_hyper3d_status":
        key_reader = getattr(server, "_get_hyper3d_api_key", None)
        if not callable(key_reader) or not key_reader():
            return {"state": "configuration_required", "statusText": "需要配置"}
        return ({"state": "ready", "statusText": "已配置"} if enabled else
                {"state": "disabled", "statusText": "未启用"})

    if command == "get_hunyuan3d_status":
        mode = getattr(scene, "blendermcp_hunyuan3d_mode", "OFFICIAL_API")
        if mode == "LOCAL_API":
            url_reader = getattr(server, "_get_hunyuan3d_api_url", None)
            configured = callable(url_reader) and bool(url_reader())
        else:
            id_reader = getattr(server, "_get_hunyuan3d_secret_id", None)
            key_reader = getattr(server, "_get_hunyuan3d_secret_key", None)
            configured = (callable(id_reader) and callable(key_reader)
                          and bool(id_reader()) and bool(key_reader()))
        if not configured:
            return {"state": "configuration_required", "statusText": "需要配置"}
        return ({"state": "ready", "statusText": "已配置"} if enabled else
                {"state": "disabled", "statusText": "未启用"})

    status_reader = getattr(server, command, None)
    if not callable(status_reader):
        return None
    result = status_reader()
    if not isinstance(result, dict):
        raise ProviderRegistryError("community status method returned an invalid result")
    return _community_status(
        result, ready_text="可用" if command == "get_polyhaven_status" else "已配置",
    )


def _community_status_probe(command: str, metadata: dict | None = None):
    if not isinstance(command, str) or STATUS_COMMAND.fullmatch(command) is None:
        raise ProviderRegistryError("community statusCommand is invalid")
    probe_metadata = dict(metadata or {})

    def probe(context) -> dict:
        direct = _in_process_community_status(command, probe_metadata, context)
        if direct is not None:
            return direct
        payload = json.dumps({"type": command, "params": {}}, separators=(",", ":")) + "\n"
        try:
            with socket.create_connection(("127.0.0.1", 9876), timeout=0.5) as connection:
                connection.settimeout(1.0)
                connection.sendall(payload.encode("utf-8"))
                chunks = bytearray()
                while not chunks.endswith(b"\n"):
                    block = connection.recv(65536)
                    if not block:
                        break
                    chunks.extend(block)
        except OSError:
            return {"state": "unavailable", "statusText": "社区服务未连接"}
        try:
            envelope = json.loads(chunks.decode("utf-8", "replace").strip())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"state": "error", "statusText": "状态响应无效"}
        if envelope.get("status") != "success" or not isinstance(envelope.get("result"), dict):
            return {"state": "error", "statusText": "状态检查失败"}
        return _community_status(
            envelope["result"],
            ready_text="可用" if command == "get_polyhaven_status" else "已配置",
        )

    return probe


def _partme_provider_status(provider_id):
    def probe(context):
        addons = getattr(getattr(context, "preferences", None), "addons", {})
        preferences = getattr(addons.get("partme_blender_mcp"), "preferences", None)
        if provider_id == "polyhaven":
            configured = True
        elif provider_id == "hyper3d":
            oauth = getattr(preferences, "hyper3d_auth_mode", "API_KEY") == "MCP_OAUTH"
            if oauth:
                authorized = getattr(preferences, "hyper3d_oauth_status", "NOT_AUTHORIZED") == "AUTHORIZED"
                # The client owning an OAuth grant is not proof that its MCP
                # transport completed initialize/initialized and can list or
                # call tools. Keep it out of the available-provider count until
                # a real client connectivity probe supplies that evidence.
                return ({"state": "unavailable", "statusText": "OAuth 已授权 · 客户端连接待验证"} if authorized else
                        {"state": "configuration_required", "statusText": "等待客户端 OAuth 授权"})
            configured = bool(getattr(preferences, "hyper3d_api_key", "").strip())
        elif provider_id == "sketchfab":
            oauth = getattr(preferences, "sketchfab_auth_mode", "API_TOKEN") == "OAUTH"
            if oauth:
                authorized = (getattr(preferences, "sketchfab_oauth_status", "NOT_AUTHORIZED") == "AUTHORIZED"
                              and bool(getattr(preferences, "sketchfab_access_token", "").strip()))
                return ({"state": "ready", "statusText": "OAuth 已授权"} if authorized else
                        {"state": "configuration_required", "statusText": "等待 Sketchfab OAuth 授权"})
            configured = bool(getattr(preferences, "sketchfab_api_key", "").strip())
        elif provider_id == "hunyuan3d":
            local = getattr(preferences, "hunyuan3d_mode", "OFFICIAL_API") == "LOCAL_API"
            tokenhub = getattr(preferences, "hunyuan3d_auth_mode", "TENCENT_CLOUD_API") == "TOKENHUB_API_KEY"
            if not local and tokenhub:
                configured = bool(getattr(preferences, "hunyuan3d_tokenhub_api_key", "").strip())
                if not configured:
                    return {"state": "configuration_required", "statusText": "需要配置 TokenHub API Key"}
            configured = (bool(getattr(preferences, "hunyuan3d_api_url", "").strip()) if local else
                          bool(getattr(preferences, "hunyuan3d_secret_id", "").strip()
                               and getattr(preferences, "hunyuan3d_secret_key", "").strip()))
        else:
            configured = bool(getattr(preferences, provider_id + "_api_key", "").strip())
        if not configured:
            return {"state": "configuration_required", "statusText": "需要配置凭证"}
        try:
            importlib.import_module('partme_blender_mcp.provider_engine')
        except ImportError:
            return {"state": "unavailable", "statusText": "凭证已配置；执行器未加载"}
        if provider_id == 'polyhaven':
            return {"state": "ready", "statusText": "可用（未验证网络）"}
        return {"state": "ready", "statusText": "已配置（未验证远端凭证）"}
    return probe


def register_native_providers(registry: ProviderRegistry) -> None:
    registry.register(ProviderDefinition(
        provider_id="local_library", label="本地素材库", category="asset_library", source="native",
        risks=("read", "scene_import"), mutable=False, status_probe=_asset_root_status,
        metadata={"uiOrder": 10},
    ))
    registry.register(ProviderDefinition(
        provider_id="polypizza", label="Poly Pizza", category="asset_library", source="native",
        risks=("read", "network_download", "scene_import"), actions=("configure",),
        enabled=True, configurable=True, status_probe=_polypizza_status,
        metadata={"uiOrder": 40},
    ))


_REGISTRY = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    return _REGISTRY


def reload_provider_registry(contribution_path: Path | None = None) -> ProviderRegistry:
    _REGISTRY.clear()
    register_native_providers(_REGISTRY)
    if contribution_path is not None and Path(contribution_path).is_file():
        _REGISTRY.load(Path(contribution_path))
    return _REGISTRY
