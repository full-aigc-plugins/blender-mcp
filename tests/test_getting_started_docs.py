import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE_DIR = ROOT / "docs" / "getting-started"
GUIDES = (
    "codex.zh-CN.md",
    "claude-desktop.zh-CN.md",
    "claude-code.zh-CN.md",
    "minimax-design.zh-CN.md",
    "cursor.zh-CN.md",
    "generic-mcp.zh-CN.md",
    "macos.zh-CN.md",
    "windows.zh-CN.md",
)
CLIENT_GUIDES = GUIDES[:6]
PROHIBITED = ("/Users/wandl", ".codex/plugins/cache", "codex-blender-connector", "blender__")


def text(name: str) -> str:
    return (GUIDE_DIR / name).read_text(encoding="utf-8")


class SourceRegistryTests(unittest.TestCase):
    def test_sources_are_explicit_and_evidence_scoped(self):
        data = json.loads((GUIDE_DIR / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(data["product"], "PartMe Blender MCP")
        self.assertEqual(data["releaseUrl"], "https://github.com/full-aigc-plugins/blender-mcp/releases/latest")
        self.assertEqual(data["blenderDownloadUrl"], "https://www.blender.org/download/")
        self.assertIn("2025-06-18", data["mcpProtocolUrl"])
        self.assertEqual(
            set(data["clients"]),
            {"codex", "claudeDesktop", "claudeCode", "minimaxDesign", "cursor", "generic"},
        )
        self.assertEqual(data["clients"]["codex"]["status"], "VERIFIED")
        for client in ("claudeDesktop", "claudeCode", "minimaxDesign", "cursor", "generic"):
            self.assertEqual(data["clients"][client]["status"], "DOCUMENTED_NOT_RUN")


class GuideContractTests(unittest.TestCase):
    def test_all_requested_guides_and_index_exist(self):
        for name in (*GUIDES, "README.zh-CN.md"):
            self.assertTrue((GUIDE_DIR / name).is_file(), name)

    def test_guides_use_neutral_identity_and_no_developer_paths(self):
        for name in GUIDES:
            body = text(name)
            self.assertIn("PartMe Blender MCP", body, name)
            self.assertNotIn("Codex Blender Connector", body, name)
            for prohibited in PROHIBITED:
                self.assertNotIn(prohibited, body, name)

    def test_client_guides_link_platforms_and_define_read_only_smoke(self):
        for name in CLIENT_GUIDES:
            body = text(name)
            self.assertIn("macos.zh-CN.md", body, name)
            self.assertIn("windows.zh-CN.md", body, name)
            self.assertIn("partme_blender", body, name)
            self.assertIn("blender_connection_status", body, name)
            self.assertIn("blender_scene_inspect", body, name)
            self.assertRegex(body, r"\b(?:VERIFIED|DOCUMENTED_NOT_RUN|UNAVAILABLE)\b", name)

    def test_all_relative_markdown_targets_exist(self):
        pattern = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
        for markdown in ROOT.glob("docs/**/*.md"):
            for raw in pattern.findall(markdown.read_text(encoding="utf-8")):
                target = raw.strip().split("#", 1)[0]
                if not target or "://" in target or target.startswith("#") or target.startswith("mailto:"):
                    continue
                resolved = (markdown.parent / target).resolve()
                self.assertTrue(resolved.is_relative_to(ROOT.resolve()), f"{markdown}: {raw}")
                self.assertTrue(resolved.exists(), f"{markdown}: missing {raw}")


class PlatformGuideTests(unittest.TestCase):
    def test_macos_has_checksum_blender_and_screenshot_steps(self):
        body = text("macos.zh-CN.md")
        for expected in (
            "shasum -a 256",
            "https://www.blender.org/download/",
            "从磁盘安装",
            "Start MCP Server",
            "../assets/reference/blender-open-preferences.png",
            "../assets/reference/blender-install-from-disk.png",
        ):
            self.assertIn(expected, body)

    def test_windows_has_checksum_named_pipe_and_honest_status(self):
        body = text("windows.zh-CN.md")
        for expected in ("Get-FileHash", "Named Pipe", "DOCUMENTED_NOT_RUN", "Start MCP Server"):
            self.assertIn(expected, body)
        self.assertNotIn("打开防火墙端口", body)


class CodexGuideTests(unittest.TestCase):
    def test_codex_uses_current_cli_contract(self):
        body = text("codex.zh-CN.md")
        self.assertIn("codex mcp add partme_blender -- python -m partme_blender_mcp", body)
        self.assertIn("codex mcp get partme_blender", body)
        self.assertIn("codex mcp remove partme_blender", body)
        self.assertIn("新建", body)


class ClaudeGuideTests(unittest.TestCase):
    def test_desktop_prefers_dxt_and_distinguishes_remote_connectors(self):
        body = text("claude-desktop.zh-CN.md")
        for expected in (".dxt", "Settings", "Extensions", "DOCUMENTED_NOT_RUN", "远程 Connector"):
            self.assertIn(expected, body)

    def test_code_uses_official_option_order(self):
        body = text("claude-code.zh-CN.md")
        self.assertIn(
            "claude mcp add --transport stdio --scope user partme_blender -- python -m partme_blender_mcp",
            body,
        )
        self.assertIn("claude mcp list", body)
        self.assertIn("/mcp", body)


class MiniMaxGuideTests(unittest.TestCase):
    def test_minimax_uses_observed_fields_and_both_images(self):
        body = text("minimax-design.zh-CN.md")
        for expected in (
            "../assets/reference/minimax-design-add-custom-connector.png",
            "../assets/reference/minimax-design-transport-options.png",
            "启动命令",
            "启动参数",
            "Streamable HTTP",
            "SSE",
            "DOCUMENTED_NOT_RUN",
        ):
            self.assertIn(expected, body)
        self.assertRegex(body, r"(?s)首版.*仅.*stdio")


class CursorAndGenericGuideTests(unittest.TestCase):
    def test_cursor_has_global_project_and_cli_checks(self):
        body = text("cursor.zh-CN.md")
        for expected in (
            "~/.cursor/mcp.json",
            ".cursor/mcp.json",
            "cursor-agent mcp list",
            "cursor-agent mcp list-tools partme_blender",
        ):
            self.assertIn(expected, body)

    def test_generic_documents_full_stdio_lifecycle(self):
        body = text("generic-mcp.zh-CN.md")
        for expected in (
            "initialize",
            "notifications/initialized",
            "tools/list",
            "nextCursor",
            "tools/call",
            "structuredContent",
            "annotations",
            "stderr",
        ):
            self.assertIn(expected, body)


if __name__ == "__main__":
    unittest.main()

