import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.5.0"


class RepositoryStructureTests(unittest.TestCase):
    def test_runtime_and_release_sources_exist(self):
        required = (
            "pyproject.toml",
            "README.md",
            "README.zh-CN.md",
            "LICENSE",
            "SECURITY.md",
            "src/partme_blender_mcp/__init__.py",
            "src/partme_blender_mcp/__main__.py",
            "src/partme_blender_mcp/harness/mcp_adapter.py",
            "addon/partme_blender_mcp/__init__.py",
            "addon/partme_blender_mcp/panel.py",
            "scripts/package_release.py",
            "installers/macos/install_partme_blender_mcp.command",
            "installers/windows/install_partme_blender_mcp.bat",
            "installers/windows/install_partme_blender_mcp.ps1",
            ".github/workflows/release.yml",
        )
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_brand_assets_exist_and_are_not_placeholders(self):
        for name in ("logo.png", "hero.png", "cover.png", "architecture.png"):
            target = ROOT / "assets" / "brand" / name
            self.assertTrue(target.is_file(), name)
            self.assertGreater(target.stat().st_size, 100_000, name)


class RuntimeContractTests(unittest.TestCase):
    def test_package_version_and_neutral_identity(self):
        # Identity lives inside harness/ so the installed Blender Add-on resolves it too.
        version_path = ROOT / "src/partme_blender_mcp/harness/version.py"
        spec = importlib.util.spec_from_file_location("partme_blender_mcp_version", version_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.__version__, VERSION)
        self.assertEqual(module.PRODUCT_NAME, "PartMe Blender MCP")
        self.assertEqual(module.MCP_SERVER_ID, "partme_blender")
        init_text = (ROOT / "src/partme_blender_mcp/__init__.py").read_text(encoding="utf-8")
        self.assertIn("from .harness.version import", init_text, "public identity must re-export the single source")

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "official MCP SDK is not installed")
    def test_stdio_entrypoint_initializes_and_lists_single_underscore_tools(self):
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        process = subprocess.Popen(
            [sys.executable, "-m", "partme_blender_mcp"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=ROOT,
        )
        try:
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                           "clientInfo": {"name": "release-test", "version": "1"}}}) + "\n")
            process.stdin.flush()
            initialized = json.loads(process.stdout.readline())
            self.assertEqual(initialized["result"]["serverInfo"]["name"], "partme-blender-mcp")
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
            process.stdin.flush()
            listing = json.loads(process.stdout.readline())
            names = [tool["name"] for tool in listing["result"]["tools"]]
            self.assertIn("blender_connection_status", names)
            self.assertFalse(any("__" in name for name in names))
        finally:
            process.stdin.close()
            self.assertEqual(process.wait(timeout=10), 0, process.stderr.read())
            process.stdout.close()
            process.stderr.close()

    def test_public_catalog_is_vendor_neutral_and_complete(self):
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from partme_blender_mcp.harness.mcp_adapter import McpAdapter
            tools = McpAdapter(plugin_root=ROOT).tools
        finally:
            sys.path.pop(0)
        commands = [tool for tool in tools if tool.get("_meta", {}).get("codexBlenderCommand")]
        self.assertEqual(len(commands), 168)
        self.assertFalse(any("official_uploader" in tool["name"] for tool in commands))
        self.assertNotIn("blender_advanced_execute_python", {tool["name"] for tool in commands})
        self.assertNotIn("blender_authorize", {tool["name"] for tool in tools})

    def test_cli_version_help_and_doctor_are_non_blocking(self):
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        version = subprocess.run(
            [sys.executable, "-m", "partme_blender_mcp", "--version"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), f"PartMe Blender MCP {VERSION}")
        help_result = subprocess.run(
            [sys.executable, "-m", "partme_blender_mcp", "--help"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("doctor --json", help_result.stdout)
        doctor = subprocess.run(
            [sys.executable, "-m", "partme_blender_mcp", "doctor", "--json"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        payload = json.loads(doctor.stdout)
        self.assertEqual(payload["product"], "PartMe Blender MCP")
        self.assertIn("blenderInstalled", payload)
        self.assertIn("connection", payload)


class ReleasePackageTests(unittest.TestCase):
    def test_release_builder_creates_verified_installers(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/package_release.py"), "--output", directory],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = Path(directory)
            names = {
                f"partme-blender-mcp-addon-{VERSION}.zip",
                f"partme-blender-mcp-runtime-{VERSION}.zip",
                f"partme-blender-mcp-macos-arm64-{VERSION}.tar.gz",
                f"partme-blender-mcp-windows-x64-{VERSION}.zip",
                "runtime-manifest.json",
                "SHA256SUMS.txt",
                "SBOM.spdx.json",
                "partme-community-addon-2.0.0.zip",
            }
            self.assertEqual({path.name for path in output.iterdir()}, names)
            sums = {}
            for line in (output / "SHA256SUMS.txt").read_text().splitlines():
                digest, name = line.split("  ", 1)
                sums[name] = digest
            for name in names - {"SHA256SUMS.txt"}:
                digest = hashlib.sha256((output / name).read_bytes()).hexdigest()
                self.assertEqual(sums[name], digest, name)
            manifest = json.loads((output / "runtime-manifest.json").read_text())
            self.assertEqual(manifest["version"], VERSION)
            self.assertEqual(manifest["product"], "PartMe Blender MCP")
            with zipfile.ZipFile(output / f"partme-blender-mcp-addon-{VERSION}.zip") as archive:
                archive_names = set(archive.namelist())
                self.assertIn("partme_blender_mcp/__init__.py", archive_names)
                self.assertIn("partme_blender_mcp/panel.py", archive_names)
                self.assertIn("partme_blender_mcp/harness/server.py", archive_names)
            with zipfile.ZipFile(output / f"partme-blender-mcp-runtime-{VERSION}.zip") as archive:
                self.assertIn("pyproject.toml", archive.namelist())
                self.assertIn("src/partme_blender_mcp/__main__.py", archive.namelist())

    def test_platform_bundles_are_self_describing_python_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/package_release.py"), "--output", directory],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            mac_bundle = output / f"partme-blender-mcp-macos-arm64-{VERSION}.tar.gz"
            windows_bundle = output / f"partme-blender-mcp-windows-x64-{VERSION}.zip"
            with tarfile.open(mac_bundle, "r:gz") as archive:
                names = set(archive.getnames())
            self.assertIn("pyproject.toml", names)
            self.assertIn("README-FIRST.txt", names)
            with zipfile.ZipFile(windows_bundle) as archive:
                names = set(archive.namelist())
            self.assertIn("pyproject.toml", names)
            self.assertIn("README-FIRST.txt", names)


class ReadmeContractTests(unittest.TestCase):
    def test_bilingual_readmes_follow_the_plugin_entry_path(self):
        expected = (
            "Positioning", "At a glance", "Capabilities and boundaries", "Installation",
            "Quick start", "Security and recovery", "Errors and troubleshooting",
            "Development, verification, and release", "Repository map",
            "Compatibility and migration", "Contributing and license",
        )
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^# ", english, re.MULTILINE)), 1)
        self.assertEqual(len(re.findall(r"^# ", chinese, re.MULTILINE)), 1)
        for heading in expected:
            self.assertIn(f"## {heading}", english)
        for phrase in ("项目定位", "一眼看懂", "核心能力与边界", "安装", "快速开始",
                       "安全、事务与恢复", "错误与排查", "开发、测试与发布", "项目结构",
                       "兼容与迁移", "贡献与许可证"):
            self.assertIn(f"## {phrase}", chinese)
        for body in (english, chinese):
            self.assertNotIn("{{", body)
            self.assertNotIn("/Users/", body)
            for image in ("assets/brand/hero.png", "assets/brand/architecture.png"):
                self.assertIn(image, body)

    def test_readme_relative_links_resolve(self):
        pattern = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
        for filename in ("README.md", "README.zh-CN.md"):
            path = ROOT / filename
            for raw in pattern.findall(path.read_text(encoding="utf-8")):
                target = raw.split("#", 1)[0]
                if not target or "://" in target:
                    continue
                self.assertTrue((ROOT / target).exists(), f"{filename}: {raw}")


if __name__ == "__main__":
    unittest.main()
