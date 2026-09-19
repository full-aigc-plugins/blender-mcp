import json
import tempfile
import sys
import unittest
from pathlib import Path

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
        self.assertEqual(registry.snapshot()["summary"], {"ready": 0, "total": 1, "busy": 1})

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


class ProviderPanelContractTests(unittest.TestCase):
    def test_addon_exposes_generic_child_panels(self):
        panel = (Path(__file__).resolve().parents[1] / "addon/partme_blender_mcp/panel.py").read_text(encoding="utf-8")
        self.assertIn('bl_label = "权限与执行"', panel)
        self.assertIn('bl_label = "资产与素材库"', panel)
        self.assertIn('bl_label = "AI 生成模型"', panel)
        self.assertGreaterEqual(panel.count('bl_parent_id = "VIEW3D_PT_partme_blender_mcp"'), 3)
        self.assertNotIn("blendermcp_use_polypizza", panel)

    def test_finalized_ui_defaults_open_and_exposes_real_generic_task_controls(self):
        root = Path(__file__).resolve().parents[1]
        panel = (root / "addon/partme_blender_mcp/panel.py").read_text(encoding="utf-8")
        frontend = (root / "src/partme_blender_mcp/harness/frontend.py").read_text(encoding="utf-8")

        self.assertNotIn("DEFAULT_CLOSED", panel)
        self.assertIn("partme_blender_asset_strategy", panel)
        self.assertIn("PARTMEBLENDER_OT_cancel_provider_task", panel)
        self.assertIn("自动搜索与生成", panel)
        self.assertIn("供应商能力", panel)
        self.assertIn("layout.progress", panel)
        for label in ("相机", "正面", "侧面", "顶面", "播放 / 暂停动画", "快捷操作"):
            self.assertIn(label, frontend)
        self.assertNotIn('box.label(text="无待批准操作"', frontend)


if __name__ == "__main__":
    unittest.main()
