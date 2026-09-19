"""Real-Blender smoke for provider preferences and community enable-property synchronization."""

import json
import sys
from pathlib import Path


ADDON_ROOT = None
if "--" in sys.argv:
    ADDON_ROOT = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
if ADDON_ROOT is None or not (ADDON_ROOT / "partme_blender_mcp").is_dir():
    raise SystemExit("pass the directory containing both Add-on packages after '--'")
sys.path.insert(0, str(ADDON_ROOT))

import bpy  # noqa: E402


report = {"blender": bpy.app.version_string}
bpy.ops.preferences.addon_enable(module="blender_mcp_community")
bpy.ops.preferences.addon_enable(module="partme_blender_mcp")

from partme_blender_mcp.harness.provider_registry import get_provider_registry  # noqa: E402


registry = get_provider_registry()
snapshot = registry.snapshot(bpy.context)
report["providerIds"] = [row["providerId"] for row in snapshot["providers"]]
report["defaultTab"] = bpy.context.window_manager.partme_blender_ui_tab
preferences = bpy.context.preferences.addons["partme_blender_mcp"].preferences
from partme_blender_mcp.panel import _deferred_provider_sync  # noqa: E402
report["providerSyncScheduled"] = bpy.app.timers.is_registered(_deferred_provider_sync)
report["providerSyncCompleted"] = _deferred_provider_sync() is None
report["polyhavenDefaultApplied"] = bool(bpy.context.scene.blendermcp_use_polyhaven)

toggle_result = bpy.ops.partme_blender.set_provider_enabled(provider_id="polyhaven", enabled=False)
polyhaven = next(row for row in registry.snapshot(bpy.context)["providers"] if row["providerId"] == "polyhaven")
report["polyhavenToggleResult"] = list(toggle_result)
report["polyhavenRuntimeDisabled"] = not bpy.context.scene.blendermcp_use_polyhaven
report["polyhavenRegistryDisabled"] = not polyhaven["enabled"] and polyhaven["state"] == "disabled"

report["preferencePersisted"] = json.loads(preferences.provider_enabled_json).get("polyhaven") is False

bpy.ops.preferences.addon_disable(module="partme_blender_mcp")
bpy.ops.preferences.addon_disable(module="blender_mcp_community")
report["addonsDisabled"] = all(
    module not in bpy.context.preferences.addons for module in ("partme_blender_mcp", "blender_mcp_community")
)

required = {
    "defaultTab": "WORK",
    "providerSyncScheduled": True,
    "providerSyncCompleted": True,
    "polyhavenDefaultApplied": True,
    "polyhavenToggleResult": ["FINISHED"],
    "polyhavenRuntimeDisabled": True,
    "polyhavenRegistryDisabled": True,
    "preferencePersisted": True,
    "addonsDisabled": True,
}
print("PROVIDER_TOGGLE_SMOKE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
for key, expected in required.items():
    if report.get(key) != expected:
        raise RuntimeError(f"provider smoke failed: {key}={report.get(key)!r}, expected {expected!r}")
