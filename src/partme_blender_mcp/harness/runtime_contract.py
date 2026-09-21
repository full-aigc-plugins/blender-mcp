"""Content-addressed contract shared by the Blender Add-on and MCP Runtime."""

from __future__ import annotations

import hashlib
import json

from .version import HARNESS_PROTOCOL_VERSION, __version__


class RuntimeContractError(ValueError):
    """A private session descriptor does not match the running MCP Runtime."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def normalize_capabilities(capabilities) -> list[dict]:
    """Return the stable command/risk manifest used for negotiation and hashing."""
    if not isinstance(capabilities, list):
        raise RuntimeContractError(
            "ADDON_RUNTIME_CAPABILITY_MISMATCH",
            "Add-on capability manifest must be an array",
        )
    normalized = []
    seen = set()
    for item in capabilities:
        if not isinstance(item, dict):
            raise RuntimeContractError(
                "ADDON_RUNTIME_CAPABILITY_MISMATCH",
                "Add-on capability entries must be objects",
            )
        command, risk = item.get("command"), item.get("risk")
        if not isinstance(command, str) or not command or risk not in {"read", "standard", "gated"}:
            raise RuntimeContractError(
                "ADDON_RUNTIME_CAPABILITY_MISMATCH",
                "Add-on capability entries require a command and valid risk",
            )
        if command in seen:
            raise RuntimeContractError(
                "ADDON_RUNTIME_CAPABILITY_MISMATCH",
                f"Add-on capability manifest repeats command: {command}",
            )
        seen.add(command)
        normalized.append({"command": command, "risk": risk})
    return sorted(normalized, key=lambda item: item["command"])


def capability_sha256(capabilities) -> str:
    """Hash one normalized manifest with a platform-independent encoding."""
    normalized = normalize_capabilities(capabilities)
    encoded = json.dumps(
        normalized, ensure_ascii=True, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_runtime_contract(capabilities) -> dict:
    """Build descriptor fields proving the Add-on version and callable commands."""
    normalized = normalize_capabilities(capabilities)
    return {
        "runtimeVersion": __version__,
        "harnessProtocolVersion": HARNESS_PROTOCOL_VERSION,
        "capabilities": normalized,
        "capabilitiesSha256": capability_sha256(normalized),
    }


def validate_runtime_contract(descriptor: dict) -> list[dict]:
    """Validate a descriptor and return its normalized capability manifest."""
    required = {
        "runtimeVersion", "harnessProtocolVersion", "capabilities", "capabilitiesSha256",
    }
    if required.difference(descriptor):
        raise RuntimeContractError(
            "ADDON_RUNTIME_VERSION_MISMATCH",
            f"Blender Add-on does not publish the Runtime contract required by {__version__}; install the matching Add-on",
        )
    installed = descriptor.get("runtimeVersion")
    protocol = descriptor.get("harnessProtocolVersion")
    if installed != __version__ or protocol != HARNESS_PROTOCOL_VERSION:
        raise RuntimeContractError(
            "ADDON_RUNTIME_VERSION_MISMATCH",
            f"Blender Add-on {installed!r} is incompatible with Runtime {__version__!r}; install matching versions",
        )
    normalized = normalize_capabilities(descriptor.get("capabilities"))
    expected_hash = capability_sha256(normalized)
    if descriptor.get("capabilitiesSha256") != expected_hash:
        raise RuntimeContractError(
            "ADDON_RUNTIME_CAPABILITY_MISMATCH",
            "Blender Add-on capability manifest hash is invalid; reinstall the matching Add-on",
        )
    return normalized
