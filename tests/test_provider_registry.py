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


class ProviderPanelContractTests(unittest.TestCase):
    def test_addon_exposes_generic_child_panels(self):
        panel = (Path(__file__).resolve().parents[1] / "addon/partme_blender_mcp/panel.py").read_text(encoding="utf-8")
        self.assertIn('bl_label = "权限与执行"', panel)
        self.assertIn('bl_label = "资产与素材库"', panel)
        self.assertIn('bl_label = "AI 生成模型"', panel)
        self.assertGreaterEqual(panel.count('bl_parent_id = "VIEW3D_PT_partme_blender_mcp"'), 3)
        self.assertNotIn("blendermcp_use_polypizza", panel)


if __name__ == "__main__":
    unittest.main()
