"""Provider catalog and secret-free status protocol shared by Blender surfaces."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


PROVIDER_STATUS_SCHEMA = "partme-provider-status/v1"
PROVIDER_CATALOG_SCHEMA = "partme-provider-catalog/v1"
VALID_CATEGORIES = {"asset_library", "ai_model"}
VALID_SOURCES = {"native", "community"}
VALID_STATES = {"ready", "disabled", "configuration_required", "unavailable", "busy", "error"}
VALID_RISKS = {"read", "network_download", "paid_generation", "scene_import", "external_export"}
SECRET_KEY = re.compile(r"(?:api.?key|token|secret|password|credential)", re.IGNORECASE)


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
    def __init__(self):
        self._providers: dict[str, ProviderDefinition] = {}

    def clear(self) -> None:
        self._providers.clear()

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
            self.register(ProviderDefinition(
                provider_id=item.get("providerId", ""),
                label=item.get("label", ""),
                category=item.get("category", ""),
                source=item.get("source", ""),
                risks=tuple(item.get("risks", ())),
                status=dict(item.get("status") or {"state": "unavailable", "statusText": "不可用"}),
                actions=tuple(item.get("actions", ())),
                metadata=dict(item.get("metadata") or {}),
            ))

    def snapshot(self, context=None) -> dict:
        rows = []
        for definition in self._providers.values():
            status = dict(definition.status)
            if definition.status_probe is not None:
                try:
                    probed = definition.status_probe(context)
                    if isinstance(probed, dict):
                        status.update(probed)
                except Exception:
                    status = {"state": "error", "statusText": "状态检查失败"}
            if status.get("state") not in VALID_STATES:
                status = {"state": "error", "statusText": "状态协议错误"}
            rows.append({
                "schemaVersion": PROVIDER_STATUS_SCHEMA,
                "providerId": definition.provider_id,
                "label": definition.label,
                "category": definition.category,
                "source": definition.source,
                "state": status["state"],
                "statusText": str(status.get("statusText") or status["state"]),
                "risks": list(definition.risks),
                "actions": list(definition.actions),
                "metadata": dict(definition.metadata),
            })
        return {"schemaVersion": PROVIDER_STATUS_SCHEMA, "providers": rows}


def _asset_root_status(context) -> dict:
    scene = getattr(context, "scene", None)
    root = getattr(scene, "partme_blender_asset_root", "") if scene is not None else ""
    return ({"state": "ready", "statusText": "PartMe 原生"} if root else
            {"state": "configuration_required", "statusText": "需要素材目录"})


def _polypizza_status(_context) -> dict:
    return ({"state": "ready", "statusText": "PartMe 原生"} if os.environ.get("POLYPIZZA_API_KEY") else
            {"state": "configuration_required", "statusText": "需要 API Key"})


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
