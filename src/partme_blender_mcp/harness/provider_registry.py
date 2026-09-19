"""Provider catalog and secret-free status protocol shared by Blender surfaces."""

from __future__ import annotations

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
        if _contains_secret(self.metadata):
            raise ProviderRegistryError("provider metadata must not contain credentials")


class ProviderRegistry:
    def __init__(self, *, task_registry: ProviderTaskRegistry | None = None):
        self._providers: dict[str, ProviderDefinition] = {}
        self._status_overrides: dict[str, dict] = {}
        self._task_registry = task_registry or get_provider_task_registry()

    def clear(self) -> None:
        self._providers.clear()
        self._status_overrides.clear()

    def register(self, definition: ProviderDefinition) -> None:
        if definition.provider_id in self._providers:
            raise ProviderRegistryError(f"provider already registered: {definition.provider_id}")
        self._providers[definition.provider_id] = definition

    def load(self, path: Path) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != PROVIDER_CATALOG_SCHEMA or not isinstance(payload.get("providers"), list):
            raise ProviderRegistryError("provider catalog schema is invalid")
        for item in payload["providers"]:
            allowed = {"providerId", "label", "category", "source", "risks", "status", "actions", "metadata"}
            if not isinstance(item, dict) or set(item) - allowed:
                raise ProviderRegistryError("provider contribution contains unknown fields")
            metadata = dict(item.get("metadata") or {})
            status_probe = None
            if item.get("source") == "community" and metadata.get("statusCommand"):
                status_probe = _community_status_probe(metadata["statusCommand"])
            self.register(ProviderDefinition(
                provider_id=item.get("providerId", ""),
                label=item.get("label", ""),
                category=item.get("category", ""),
                source=item.get("source", ""),
                risks=tuple(item.get("risks", ())),
                status=dict(item.get("status") or {"state": "unavailable", "statusText": "不可用"}),
                actions=tuple(item.get("actions", ())),
                metadata=metadata,
                status_probe=status_probe,
            ))

    def snapshot(self, context=None) -> dict:
        rows = []
        for definition in self._providers.values():
            status = dict(definition.status)
            status.update(self._status_overrides.get(definition.provider_id, {}))
            if status.get("state") not in VALID_STATES:
                status = {"state": "error", "statusText": "状态协议错误"}
            actions = list(definition.actions)
            task = self._task_registry.latest(definition.provider_id)
            if task is not None and task["active"]:
                status = {"state": "busy", "statusText": task.get("statusText") or task.get("stage") or "处理中"}
                if "cancel" not in actions:
                    actions.append("cancel")
            row = {
                "schemaVersion": PROVIDER_STATUS_SCHEMA,
                "providerId": definition.provider_id,
                "label": definition.label,
                "category": definition.category,
                "source": definition.source,
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
                "ready": sum(row["state"] == "ready" for row in rows),
                "total": len(rows),
                "busy": sum(row["state"] == "busy" for row in rows),
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


def _asset_root_status(context) -> dict:
    scene = getattr(context, "scene", None)
    root = getattr(scene, "partme_blender_asset_root", "") if scene is not None else ""
    return ({"state": "ready", "statusText": "PartMe 原生"} if root else
            {"state": "configuration_required", "statusText": "需要素材目录"})


def _polypizza_status(_context) -> dict:
    return ({"state": "ready", "statusText": "PartMe 原生"} if os.environ.get("POLYPIZZA_API_KEY") else
            {"state": "configuration_required", "statusText": "需要 API Key"})


def _community_status_probe(command: str):
    if not isinstance(command, str) or STATUS_COMMAND.fullmatch(command) is None:
        raise ProviderRegistryError("community statusCommand is invalid")

    def probe(_context) -> dict:
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
        result = envelope["result"]
        if result.get("error"):
            return {"state": "error", "statusText": "状态检查失败"}
        if result.get("enabled") is True:
            return {"state": "ready", "statusText": "已配置"}
        message = str(result.get("message") or "").lower()
        needs_configuration = any(token in message for token in ("api key", "secretid", "secretkey", "not given"))
        return {
            "state": "configuration_required" if needs_configuration else "disabled",
            "statusText": "需要配置" if needs_configuration else "未启用",
        }

    return probe


def register_native_providers(registry: ProviderRegistry) -> None:
    registry.register(ProviderDefinition(
        provider_id="local_library", label="本地素材库", category="asset_library", source="native",
        risks=("read", "scene_import"), status_probe=_asset_root_status,
    ))
    registry.register(ProviderDefinition(
        provider_id="polypizza", label="Poly Pizza", category="asset_library", source="native",
        risks=("read", "network_download", "scene_import"), actions=("configure",),
        status_probe=_polypizza_status,
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
