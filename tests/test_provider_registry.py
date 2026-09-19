import json
import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from partme_blender_mcp.harness.provider_registry import (
    ProviderDefinition,
    ProviderRegistry,
    ProviderRegistryError,
    register_native_providers,
)
from partme_blender_mcp.harness.provider_tasks import ProviderTaskRegistry


class ProviderRegistryTests(unittest.TestCase):
    def test_status_protocol_groups_native_providers_without_community_polypizza(self):
        registry = ProviderRegistry()
        register_native_providers(registry)

        snapshot = registry.snapshot()

        self.assertEqual(snapshot["schemaVersion"], "partme-provider-status/v1")
        self.assertEqual([row["providerId"] for row in snapshot["providers"]], [
            "local_library", "polypizza",
        ])
        polypizza = snapshot["providers"][1]
        self.assertEqual(polypizza["source"], "native")
        self.assertIn("network_download", polypizza["risks"])

    def test_contribution_file_registers_community_providers(self):
        registry = ProviderRegistry()
        payload = {
            "schemaVersion": "partme-provider-catalog/v1",
            "providers": [{
                "providerId": "sketchfab",
                "label": "Sketchfab",
                "category": "asset_library",
                "source": "community",
                "risks": ["read", "network_download", "scene_import"],
                "status": {"state": "configuration_required", "statusText": "需要配置"},
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            registry.load(path)
        row = registry.snapshot()["providers"][0]
        self.assertEqual(row["providerId"], "sketchfab")
        self.assertEqual(row["state"], "configuration_required")

    def test_duplicates_unknown_values_and_secret_metadata_are_rejected(self):
        registry = ProviderRegistry()
        definition = ProviderDefinition(
            provider_id="polyhaven", label="Poly Haven", category="asset_library",
            source="community", risks=("read", "network_download"),
        )
        registry.register(definition)
        with self.assertRaises(ProviderRegistryError):
            registry.register(definition)
        with self.assertRaises(ProviderRegistryError):
            ProviderDefinition(
                provider_id="bad", label="Bad", category="other", source="community",
                risks=("read",),
            )
        with self.assertRaises(ProviderRegistryError):
            ProviderDefinition(
                provider_id="secret", label="Secret", category="asset_library", source="community",
                risks=("read",), metadata={"apiKey": "must-not-leak"},
            )

    def test_runtime_task_decorates_any_ai_provider_without_provider_specific_ui(self):
        tasks = ProviderTaskRegistry()
        registry = ProviderRegistry(task_registry=tasks)
        registry.register(ProviderDefinition(
            provider_id="future_model", label="Future Model", category="ai_model",
            source="community", risks=("read", "paid_generation"), actions=("configure",),
            status={"state": "ready", "statusText": "可用"},
        ))

        tasks.update({
            "operation": "start", "providerId": "future_model", "taskId": "task-1",
            "state": "generating", "progress": 0.68, "stage": "正在轮询结果",
            "cancelSupported": False,
        })

        row = registry.snapshot()["providers"][0]
        self.assertEqual(row["state"], "busy")
        self.assertEqual(row["task"]["progress"], 0.68)
        self.assertIn("cancel", row["actions"])
        self.assertEqual(registry.snapshot()["summary"], {
            "ready": 0, "total": 1, "busy": 1, "available": 1,
        })

    def test_refresh_caches_status_probe_instead_of_probing_during_draw(self):
        calls = []
        registry = ProviderRegistry()
        registry.register(ProviderDefinition(
            provider_id="future_library", label="Future Library", category="asset_library",
            source="community", risks=("read",),
            status={"state": "unavailable", "statusText": "未检查"},
            status_probe=lambda _context: calls.append("probe") or {"state": "ready", "statusText": "可用"},
        ))

        self.assertEqual(registry.snapshot()["providers"][0]["state"], "unavailable")
        self.assertEqual(calls, [])
        registry.refresh()
        self.assertEqual(calls, ["probe"])
        self.assertEqual(registry.snapshot()["providers"][0]["statusText"], "可用")

    def test_enabled_preference_is_independent_from_runtime_state_and_summary(self):
        registry = ProviderRegistry()
        registry.register(ProviderDefinition(
            provider_id="polyhaven", label="Poly Haven", category="asset_library",
            source="community", risks=("read", "network_download"),
            status={"state": "ready", "statusText": "可用"}, enabled=True,
        ))

        initial = registry.snapshot()
        self.assertTrue(initial["providers"][0]["enabled"])
        self.assertEqual(initial["summary"]["available"], 1)

        disabled = registry.set_enabled("polyhaven", False)
        self.assertFalse(disabled["enabled"])
        self.assertEqual(disabled["state"], "disabled")
        self.assertEqual(registry.snapshot()["summary"]["available"], 0)

        enabled = registry.set_enabled("polyhaven", True)
        self.assertTrue(enabled["enabled"])
        self.assertEqual(enabled["state"], "ready")
        self.assertEqual(registry.snapshot()["summary"]["available"], 1)

    def test_real_community_enable_property_is_written_and_read_from_context(self):
        context = SimpleNamespace(scene=SimpleNamespace(blendermcp_use_sketchfab=False))
        registry = ProviderRegistry()
        registry.register(ProviderDefinition(
            provider_id="sketchfab", label="Sketchfab", category="asset_library",
            source="community", risks=("read", "network_download"), enabled=False,
            status={"state": "ready", "statusText": "已配置"},
            metadata={"enableProperty": "blendermcp_use_sketchfab"},
        ))

        registry.set_enabled("sketchfab", True, context=context)

        self.assertTrue(context.scene.blendermcp_use_sketchfab)
        self.assertTrue(registry.snapshot(context)["providers"][0]["enabled"])

    def test_configuration_busy_and_always_enabled_providers_lock_toggle(self):
        tasks = ProviderTaskRegistry()
        registry = ProviderRegistry(task_registry=tasks)
        registry.register(ProviderDefinition(
            provider_id="local_library", label="本地素材库", category="asset_library",
            source="native", risks=("read",), mutable=False,
            status={"state": "ready", "statusText": "PartMe 原生"},
        ))
        registry.register(ProviderDefinition(
            provider_id="hyper3d", label="Hyper3D Rodin", category="ai_model",
            source="community", risks=("read", "paid_generation"), enabled=False,
            configurable=True,
            status={"state": "configuration_required", "statusText": "需要配置"},
        ))
        registry.register(ProviderDefinition(
            provider_id="hunyuan3d", label="腾讯混元 3D", category="ai_model",
            source="community", risks=("read", "paid_generation"), enabled=True,
            status={"state": "ready", "statusText": "可用"},
        ))
        tasks.update({
            "operation": "start", "providerId": "hunyuan3d", "taskId": "task-1",
            "state": "generating", "progress": 0.2,
        })

        rows = {row["providerId"]: row for row in registry.snapshot()["providers"]}
        self.assertTrue(rows["local_library"]["toggleLocked"])
        self.assertTrue(rows["hyper3d"]["toggleLocked"])
        self.assertTrue(rows["hunyuan3d"]["toggleLocked"])
        with self.assertRaises(ProviderRegistryError):
            registry.set_enabled("local_library", False)
        with self.assertRaisesRegex(ProviderRegistryError, "requires configuration"):
            registry.set_enabled("hyper3d", True)
        with self.assertRaises(ProviderRegistryError):
            registry.set_enabled("hunyuan3d", False)

    def test_temporarily_unavailable_provider_keeps_a_real_enable_preference(self):
        context = SimpleNamespace(scene=SimpleNamespace(blendermcp_use_polyhaven=False))
        registry = ProviderRegistry()
        registry.register(ProviderDefinition(
            provider_id="polyhaven", label="Poly Haven", category="asset_library",
            source="community", risks=("read", "network_download"), enabled=True,
            status={"state": "unavailable", "statusText": "社区服务未连接"},
            metadata={"enableProperty": "blendermcp_use_polyhaven"},
        ))

        enabled = registry.set_enabled("polyhaven", True, context=context)

        self.assertTrue(context.scene.blendermcp_use_polyhaven)
        self.assertTrue(enabled["enabled"])
        self.assertEqual(enabled["state"], "unavailable")
        with self.assertRaisesRegex(ProviderRegistryError, "unavailable"):
            registry.require_enabled("polyhaven", context=context)

    def test_disabled_provider_is_rejected_by_runtime_route_guard(self):
        registry = ProviderRegistry()
        registry.register(ProviderDefinition(
            provider_id="polypizza", label="Poly Pizza", category="asset_library",
            source="native", risks=("read", "network_download"), enabled=False,
            status={"state": "ready", "statusText": "PartMe 原生"},
        ))
        with self.assertRaisesRegex(ProviderRegistryError, "disabled"):
            registry.require_enabled("polypizza")


class ProviderPanelContractTests(unittest.TestCase):
    def test_addon_exposes_single_four_tab_workbench(self):
        panel = (Path(__file__).resolve().parents[1] / "addon/partme_blender_mcp/panel.py").read_text(encoding="utf-8")
        self.assertIn("partme_blender_ui_tab", panel)
        for value in ("WORK", "ASSETS", "MODELS", "ACCESS"):
            self.assertIn(f'("{value}"', panel)
        self.assertNotIn('bl_parent_id = "VIEW3D_PT_partme_blender_mcp"', panel)
        self.assertIn("PARTMEBLENDER_OT_execution_settings", panel)
        self.assertIn("PARTMEBLENDER_OT_set_provider_enabled", panel)
        self.assertIn("bpy.app.timers.register(_deferred_provider_sync", panel)
        self.assertIn("bpy.app.timers.unregister(_deferred_provider_sync", panel)
        self.assertIn("layout.prop_tabs_enum", panel)
        self.assertIn('if provider["configurable"]:', panel)
        self.assertNotIn("blendermcp_use_polypizza", panel)

    def test_finalized_ui_defaults_open_and_exposes_real_generic_task_controls(self):
        root = Path(__file__).resolve().parents[1]
        panel = (root / "addon/partme_blender_mcp/panel.py").read_text(encoding="utf-8")

        self.assertNotIn("DEFAULT_CLOSED", panel)
        self.assertIn("partme_blender_asset_strategy", panel)
        self.assertIn("PARTMEBLENDER_OT_cancel_provider_task", panel)
        self.assertIn("toggleLocked", panel)
        self.assertIn("summary['available']", panel)
        self.assertIn("自动搜索与生成", panel)
        self.assertIn("供应商可用", panel)
        self.assertIn("layout.progress", panel)
        self.assertIn("PARTMEBLENDER_OT_configure_remote_token", panel)
        self.assertIn("PARTMEBLENDER_OT_generate_remote_token", panel)
        self.assertIn("secrets.token_urlsafe(32)", panel)
        self.assertIn("Authorization: Bearer <token>", panel)
        self.assertIn("Token 不会写入复制地址", panel)
        for label in ("相机", "正面", "侧面", "顶面", "播放 / 暂停动画", "快捷操作"):
            self.assertIn(label, panel)
        self.assertNotIn('box.label(text="无待批准操作"', panel)


if __name__ == "__main__":
    unittest.main()
