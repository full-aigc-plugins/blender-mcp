"""腾讯混元 3D 能力注册表契约。"""
import importlib.util
import unittest
from pathlib import Path


SOURCE = Path(__file__).parents[1] / 'addon/partme_blender_mcp/hunyuan_capabilities.py'
SPEC = importlib.util.spec_from_file_location('partme_hunyuan_capabilities_test', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HunyuanCapabilityTests(unittest.TestCase):
    def test_professional_and_rapid_actions_are_independent(self):
        professional = MODULE.resolve_capability('PROFESSIONAL', 'MAINLAND', 'AI3D')
        rapid = MODULE.resolve_capability('RAPID', 'MAINLAND', 'AI3D')

        self.assertEqual(professional.submit_action, 'SubmitHunyuanTo3DProJob')
        self.assertEqual(professional.query_action, 'QueryHunyuanTo3DProJob')
        self.assertEqual(rapid.submit_action, 'SubmitHunyuanTo3DRapidJob')
        self.assertEqual(rapid.query_action, 'QueryHunyuanTo3DRapidJob')
        self.assertEqual(professional.risk, rapid.risk, 'paid_generation')

    def test_region_and_service_are_validated_before_profile_resolution(self):
        mainland = MODULE.resolve_profile('MAINLAND', 'AI3D')
        international = MODULE.resolve_profile('INTERNATIONAL', 'HUNYUAN')

        self.assertEqual(mainland.service, 'ai3d')
        self.assertEqual(mainland.region, 'ap-guangzhou')
        self.assertEqual(international.service, 'hunyuan')
        self.assertEqual(international.submit_body, {'EnablePBR': True})
        with self.assertRaisesRegex(ValueError, '不支持'):
            MODULE.resolve_profile('MAINLAND', 'HUNYUAN')

    def test_international_service_does_not_claim_rapid_support(self):
        with self.assertRaisesRegex(ValueError, '不支持'):
            MODULE.resolve_capability('RAPID', 'INTERNATIONAL', 'HUNYUAN')

    def test_tokenhub_capability_registry_covers_documented_models(self):
        self.assertEqual(MODULE.resolve_tokenhub_model('PROFESSIONAL'), 'hy-3d-3.1')
        self.assertEqual(MODULE.resolve_tokenhub_model('RAPID'), 'hy-3d-express')
        self.assertEqual(MODULE.resolve_tokenhub_model('TEXTURE'), 'hy-3d-texture')
        self.assertEqual(MODULE.resolve_tokenhub_model('UV'), 'hy-3d-uv')
        self.assertEqual(MODULE.resolve_tokenhub_model('AUTO_RIGGING'), 'hy-3d-rigging')
        self.assertEqual(MODULE.resolve_tokenhub_model('MOTION'), 'hy-3d-motion')
        self.assertEqual(MODULE.resolve_tokenhub_model('POLYGEN_MESH'), 'hy-3d-polygen-mesh')

    def test_tokenhub_is_an_independent_auth_adapter(self):
        self.assertEqual(MODULE.AUTH_ADAPTER_IDS, ('TENCENT_CLOUD_API', 'TOKENHUB_API_KEY'))


if __name__ == '__main__':
    unittest.main()
