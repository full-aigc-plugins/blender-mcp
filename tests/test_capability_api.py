"""Capability inspection accepts the JSON objects exposed by the public MCP schema."""
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from partme_blender_mcp.harness.registry import CommandRegistry


class CapabilityApiTests(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        self.registry.register("scene.probe", lambda arguments: {})

    def test_describe_coerces_json_profile_and_runtime(self):
        result = self.registry.describe_capability({
            "id": "scene.probe",
            "profile": {"excludeDomains": [], "excludeClasses": []},
            "runtime": {
                "blenderVersion": [5, 2, 1],
                "platform": "darwin",
                "architecture": "arm64",
                "runtimeMode": "managed",
            },
        })
        self.assertEqual(result["productionVerdict"]["status"], "not_production")

    def test_list_coerces_json_profile_and_runtime(self):
        result = self.registry.list_capabilities({
            "profile": {},
            "runtime": {
                "blenderVersion": [5, 2, 1],
                "platform": "darwin",
                "architecture": "arm64",
                "runtimeMode": "managed",
            },
        })
        self.assertEqual(result["items"][0]["productionVerdict"]["status"], "not_production")


if __name__ == "__main__":
    unittest.main()
