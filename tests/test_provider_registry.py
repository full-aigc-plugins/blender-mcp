import json
import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
        self.assertEqual(snapshot["providers"][0]["metadata"]["uiOrder"], 10)
        self.assertEqual(polypizza["metadata"]["uiOrder"], 40)

    def test_native_polypizza_defaults_on_only_after_configuration_is_available(self):
        registry = ProviderRegistry()
        register_native_providers(registry)

        missing = registry.refresh()
        polypizza = next(row for row in missing["providers"] if row["providerId"] == "polypizza")
        self.assertFalse(polypizza["enabled"])
        self.assertTrue(polypizza["toggleLocked"])
        self.assertEqual(polypizza["state"], "configuration_required")

        with patch.dict("os.environ", {"POLYPIZZA_API_KEY": "configured"}):
            configured = registry.refresh()
        polypizza = next(row for row in configured["providers"] if row["providerId"] == "polypizza")
        self.assertTrue(polypizza["enabled"])
        self.assertFalse(polypizza["toggleLocked"])
        self.assertEqual(polypizza["state"], "ready")

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

    def test_community_probe_uses_in_process_blender_server_without_loopback_socket(self):
        registry = ProviderRegistry()
        payload = {
            "schemaVersion": "partme-provider-catalog/v1",
            "providers": [{
                "providerId": "polyhaven",
                "label": "Poly Haven",
                "category": "asset_library",
                "source": "community",
                "risks": ["read", "network_download"],
                "metadata": {
                    "statusCommand": "get_polyhaven_status",
                    "enableProperty": "blendermcp_use_polyhaven",
                    "preferencesModule": "blender_mcp_community",
                },
            }],
        }
        server = SimpleNamespace(get_polyhaven_status=lambda: {
            "enabled": True,
            "message": "PolyHaven integration is enabled and ready to use.",
        })
        fake_bpy = SimpleNamespace(types=SimpleNamespace(blendermcp_server=server))
        context = SimpleNamespace(scene=SimpleNamespace(blendermcp_use_polyhaven=True))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            registry.load(path)
        with patch.dict(sys.modules, {"bpy": fake_bpy}), \
             patch("partme_blender_mcp.harness.provider_registry.socket.create_connection",
                   side_effect=AssertionError("loopback socket must not be used")) as connect:
            refreshed = registry.refresh(context)

        connect.assert_not_called()
        self.assertEqual(refreshed["providers"][0]["state"], "ready")
        self.assertEqual(refreshed["providers"][0]["statusText"], "可用")

    def test_sketchfab_in_process_probe_does_not_make_provider_network_request(self):
        registry = ProviderRegistry()
        payload = {
            "schemaVersion": "partme-provider-catalog/v1",
            "providers": [{
                "providerId": "sketchfab",
                "label": "Sketchfab",
                "category": "asset_library",
                "source": "community",
                "risks": ["read", "network_download"],
                "metadata": {
                    "statusCommand": "get_sketchfab_status",
                    "enableProperty": "blendermcp_use_sketchfab",
                    "preferencesModule": "blender_mcp_community",
                },
            }],
        }
        server = SimpleNamespace(_get_sketchfab_api_key=lambda: "configured-secret")
        fake_bpy = SimpleNamespace(types=SimpleNamespace(blendermcp_server=server))
        context = SimpleNamespace(scene=SimpleNamespace(blendermcp_use_sketchfab=True))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            registry.load(path)
        with patch.dict(sys.modules, {"bpy": fake_bpy}), \
             patch("partme_blender_mcp.harness.provider_registry.socket.create_connection",
                   side_effect=AssertionError("loopback socket must not be used")) as connect:
            refreshed = registry.refresh(context)

        connect.assert_not_called()
        self.assertEqual(refreshed["providers"][0]["state"], "ready")
        self.assertNotIn("configured-secret", json.dumps(refreshed))

    def test_disabled_hyper3d_still_reports_missing_configuration_and_locks_toggle(self):
        registry = ProviderRegistry()
        payload = {
            "schemaVersion": "partme-provider-catalog/v1",
            "providers": [{
                "providerId": "hyper3d",
                "label": "Hyper3D Rodin",
                "category": "ai_model",
                "source": "community",
                "risks": ["read", "paid_generation"],
                "enabled": False,
                "mutable": True,
                "configurable": True,
                "metadata": {
                    "statusCommand": "get_hyper3d_status",
                    "enableProperty": "blendermcp_use_hyper3d",
                    "preferencesModule": "blender_mcp_community",
                },
            }],
        }
        server = SimpleNamespace(_get_hyper3d_api_key=lambda: "")
        fake_bpy = SimpleNamespace(types=SimpleNamespace(blendermcp_server=server))
        context = SimpleNamespace(scene=SimpleNamespace(blendermcp_use_hyper3d=False))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            registry.load(path)
        with patch.dict(sys.modules, {"bpy": fake_bpy}):
            refreshed = registry.refresh(context)

        row = refreshed["providers"][0]
        self.assertEqual(row["state"], "configuration_required")
        self.assertFalse(row["enabled"])
        self.assertTrue(row["toggleLocked"])

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
        self.assertIn('community.sketchfab_api_key = self.api_key.strip()', panel)
        self.assertIn('community.hyper3d_api_key = self.api_key.strip()', panel)
        self.assertIn('community.hunyuan3d_secret_key = self.secret_key.strip()', panel)
        self.assertIn("PARTMEBLENDER_OT_copy_session_id", panel)
        self.assertIn("bpy.app.timers.register(_deferred_provider_sync", panel)
        self.assertIn("bpy.app.timers.unregister(_deferred_provider_sync", panel)
        self.assertIn('tabs.prop(context.window_manager, "partme_blender_ui_tab", expand=True)', panel)
        self.assertNotIn("layout.prop_tabs_enum(", panel)
        for icon in ("CAMERA_DATA", "AXIS_FRONT", "AXIS_SIDE", "AXIS_TOP"):
            self.assertIn(f'"{icon}"', panel)
        self.assertIn('if provider["configurable"] and not active:', panel)
        self.assertIn("_status_icon_value", panel)
        self.assertIn("icon_value=_status_icon_value", panel)
        self.assertIn('_status_icon_value("ready_check" if running else "disabled")', panel)
        self.assertIn('category == "ai_model"', panel)
        self.assertIn('emboss=not compact_settings', panel)
        self.assertIn('text="",', panel)
        self.assertIn('emboss=False,', panel)
        self.assertNotIn('text="开" if provider["enabled"] else "关"', panel)
        execution_dialog = panel.split("class PARTMEBLENDER_OT_execution_settings", 1)[1].split(
            "class PARTMEBLENDER_OT_remote_settings", 1,
        )[0]
        self.assertIn('title="权限与执行"', execution_dialog)
        self.assertIn('confirm_text="保存并应用"', execution_dialog)
        for label in ("输出目录", "素材目录", "执行模式", "素材策略"):
            self.assertIn(f'"{label}"', execution_dialog)
        self.assertNotIn("self.bl_rna.properties[name]", execution_dialog)
        provider_dialog = panel.split("class PARTMEBLENDER_OT_provider_settings", 1)[1].split(
            "class PARTMEBLENDER_OT_cancel_provider_task", 1,
        )[0]
        self.assertIn('title="供应商配置"', provider_dialog)
        self.assertIn('confirm_text="保存"', provider_dialog)
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
        for label in ("素材库", "AI 生成模型", "当前帧", "配置 MCP Python"):
            self.assertIn(label, panel)
        self.assertNotIn('box.label(text="无待批准操作"', panel)


if __name__ == "__main__":
    unittest.main()
