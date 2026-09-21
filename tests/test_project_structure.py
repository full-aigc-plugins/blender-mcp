"""Project structure contract: package layout, version identity, and archive integrity.

These tests encode the layout rules the project relies on. They exist because a misplaced
runtime module (``validate_model_in_blender.py`` living under ``addon/``) silently broke
re-import validation in every runtime-only install, and because the assembled Add-on
archive is only importable if relative imports resolve inside it.
"""

import ast
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/partme_blender_mcp"
ADDON = ROOT / "addon/partme_blender_mcp"


def _load_packager():
    path = ROOT / "scripts/package_release.py"
    spec = importlib.util.spec_from_file_location("partme_package_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _modules_in(entries):
    modules = set()
    for _, name in entries:
        if not name.endswith(".py"):
            continue
        parts = name[:-3].split("/")
        if parts[0] == "src":
            parts = parts[1:]  # the runtime archive keeps the src/ layout on disk
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules.add(".".join(parts))
    return modules


def _top_level_bindings(source: str):
    """Names a module defines or imports at top level, so `from package import name` resolves."""
    bound = set()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    return bound


def _package_bindings(entries, package):
    relative = package.replace(".", "/") + "/__init__.py"
    for path, name in entries:
        if name == relative or name == "src/" + relative:
            return _top_level_bindings(Path(path).read_text(encoding="utf-8"))
    return set()


def _archive_relative(archive_name):
    parts = archive_name[:-3].split("/")
    if parts[0] == "src":
        parts = parts[1:]
    return parts


def _unresolved_relative_imports(entries, modules):
    """Relative imports with no target module or binding inside the assembled archive."""
    unresolved = []
    for path, name in entries:
        if not name.endswith(".py"):
            continue
        parts = _archive_relative(name)
        owner_package = ".".join(parts[:-1] if parts[-1] == "__init__" else parts[:-1])
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.level):
                continue
            package = owner_package.split(".") if owner_package else []
            for _ in range(node.level - 1):
                package = package[:-1]
            base = ".".join(package + ([node.module] if node.module else []))
            for alias in node.names:
                if node.module:
                    candidates = [base]
                else:
                    candidates = [f"{base}.{alias.name}"]
                if any(candidate in modules for candidate in candidates):
                    continue
                if not node.module and alias.name in _package_bindings(entries, base):
                    continue
                unresolved.append(f"{name}:{node.lineno} -> {'.'.join(candidates)}")
    return unresolved


class LayoutTests(unittest.TestCase):
    def test_runtime_modules_live_only_in_src(self):
        """The Add-on tree owns Add-on code; the Harness is copied in at package time."""
        addon_modules = sorted(path.name for path in ADDON.glob("*.py"))
        self.assertEqual(addon_modules, [
            "__init__.py",
            "compat_io.py",
            "hunyuan_capabilities.py",
            "hunyuan_sdk.py",
            "hyper3d_auth.py",
            "panel.py",
            "provider_engine.py",
            "remote.py",
            "runtime.py",
            "sketchfab_auth.py",
            "tokenhub_3d.py",
            "tokenhub_auth.py",
        ])
        self.assertFalse((ADDON / "harness").exists(), "harness must not be duplicated under addon/")

    def test_reimport_validation_script_is_inside_the_runtime_package(self):
        script = SRC / "validate_model_in_blender.py"
        self.assertTrue(script.is_file(), "reimport_validator resolves this path inside src/")
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from partme_blender_mcp.harness.reimport_validator import VALIDATION_SCRIPT
        finally:
            sys.path.pop(0)
        self.assertEqual(VALIDATION_SCRIPT.resolve(), script.resolve())
        self.assertTrue(VALIDATION_SCRIPT.is_file())

    def test_version_is_defined_once_and_agrees_everywhere(self):
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from partme_blender_mcp.harness.version import VERSION_TUPLE, __version__
        finally:
            sys.path.pop(0)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIn('version = {attr = "partme_blender_mcp.harness.version.__version__"}', pyproject)
        self.assertEqual(__version__, ".".join(str(part) for part in VERSION_TUPLE))
        addon_init = (ADDON / "__init__.py").read_text(encoding="utf-8")
        import ast
        from partme_blender_mcp.harness.version import VERSION_TUPLE
        tree = ast.parse(addon_init)
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "bl_info"
                                  for target in node.targets))
        self.assertEqual(ast.literal_eval(assignment.value)["version"], VERSION_TUPLE)


class ArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.packager = _load_packager()

    def test_addon_archive_is_a_single_importable_package(self):
        entries = self.packager.addon_entries()
        catalog_path = next((source for source, name in entries
                             if name == 'partme_blender_mcp/providers.json'), None)
        self.assertIsNotNone(catalog_path, '独立 Add-on 必须内置供应商目录')
        tops = {name.split("/")[0] for _, name in entries}
        self.assertEqual(tops, {"partme_blender_mcp"}, "Blender installs exactly one top-level package")
        names = [name for _, name in entries]
        self.assertEqual(len(names), len(set(names)), "duplicate archive entries")
        modules = _modules_in(entries)
        for expected in (
            "partme_blender_mcp.harness.mcp_adapter",
            "partme_blender_mcp.harness.version",
            "partme_blender_mcp.harness.provider_tasks",
            "partme_blender_mcp.validate_model_in_blender",
            "partme_blender_mcp.__main__",
            "partme_blender_mcp.doctor",
            "partme_blender_mcp.panel",
            "partme_blender_mcp.runtime",
        ):
            self.assertIn(expected, modules)
        self.assertEqual(_unresolved_relative_imports(entries, modules), [])

    def test_addon_install_can_also_run_the_mcp_server(self):
        """Both installs of this package name must expose the same launch entry point."""
        for name in ("__main__.py", "doctor.py"):
            text = (SRC / name).read_text(encoding="utf-8")
            self.assertIn(
                "from .harness.version import", text,
                f"{name} must not depend on the runtime __init__, which the Add-on replaces",
            )

    def test_runtime_handshake_evidence_script_exists(self):
        self.assertTrue((ROOT / "tests/runtime/generic_mcp_client_handshake.py").is_file())
        self.assertIn(
            "generic_mcp_client_handshake.py",
            (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"),
        )

    def test_runtime_archive_is_importable_and_carries_no_brand_art(self):
        entries = self.packager.repository_entries()
        names = [name for _, name in entries]
        self.assertFalse(
            [name for name in names if name.startswith("assets/brand/")],
            "brand artwork is repository decoration, not runtime payload",
        )
        modules = _modules_in(entries)
        self.assertIn("partme_blender_mcp.harness.session", modules)
        self.assertEqual(_unresolved_relative_imports(entries, modules), [])

    def test_runtime_package_declares_official_mcp_sdk_dependency(self):
        import tomllib

        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["dependencies"], [
            "mcp>=2.2.0,<3",
            "tencentcloud-sdk-python-ai3d==3.1.57",
            "tencentcloud-sdk-python-common==3.1.57",
        ])
        self.assertEqual(project["requires-python"], ">=3.11,<3.14")


class CatalogIntegrityTests(unittest.TestCase):
    def test_argument_catalog_has_no_duplicate_keys(self):
        """A repeated key silently overrides an earlier schema, so clients see the wrong shape."""
        tree = ast.parse((SRC / "harness/runtime_catalog.py").read_text(encoding="utf-8"))
        duplicates = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = [key.value for key in node.keys if isinstance(key, ast.Constant)]
            repeated = sorted({key for key in keys if keys.count(key) > 1})
            if repeated:
                duplicates[f"line {node.lineno}"] = repeated
        self.assertEqual(duplicates, {})

    def test_shared_argument_shapes_survive_vendor_removal(self):
        """The vendor uploader once overrode these shared keys; keep their real shapes."""
        tree = ast.parse((SRC / "harness/runtime_catalog.py").read_text(encoding="utf-8"))
        merged = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = [key.value for key in node.keys if isinstance(key, ast.Constant)]
            if "points" in keys and "resolution" in keys and "materialIndex" in keys:
                merged = {k.value: v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant)}
                break
        self.assertIsNotNone(merged, "shared argument catalog was not found")
        resolution = ast.unparse(merged["resolution"])
        self.assertIn("integer", resolution, "curve resolution is a positive integer, not a label")
        points = ast.unparse(merged["points"])
        self.assertIn("items", points, "points requires an item schema")
        target = ast.unparse(merged["targetObjectId"])
        self.assertIn("locator", target, "targetObjectId is an object locator")

    def test_file_paths_and_camera_path_have_command_specific_schemas(self):
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from partme_blender_mcp.harness.mcp_adapter import build_tool_catalog
            catalog = {tool["name"]: tool for tool in build_tool_catalog()}
        finally:
            sys.path.pop(0)
        for tool_name in (
            "blender_asset_import_file",
            "blender_export_extended",
            "blender_tracking_load_clip",
        ):
            self.assertEqual(
                catalog[tool_name]["inputSchema"]["properties"]["path"]["type"],
                "string",
                tool_name,
            )
        self.assertEqual(
            catalog["blender_camera_follow_path"]["inputSchema"]["properties"]["path"]["type"],
            "object",
        )
        generated = catalog["blender_asset_fetch_generated"]["inputSchema"]["properties"]
        self.assertEqual(generated["url"]["type"], "string")
        self.assertEqual(generated["params"]["type"], "object")

    def test_every_public_tool_property_has_a_json_type(self):
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from partme_blender_mcp.harness.mcp_adapter import build_tool_catalog
            missing = []
            for tool in build_tool_catalog():
                for field, schema in tool.get("inputSchema", {}).get("properties", {}).items():
                    if not any(key in schema for key in ("type", "oneOf", "anyOf", "allOf", "$ref")):
                        missing.append((tool["name"], field))
        finally:
            sys.path.pop(0)
        self.assertEqual(missing, [])


class BrandingTests(unittest.TestCase):
    def test_shared_session_ui_is_partme_branded(self):
        """Session operators and the single Add-on workbench remain PartMe branded."""
        frontend = (SRC / "harness/frontend.py").read_text(encoding="utf-8")
        panel = (ADDON / "panel.py").read_text(encoding="utf-8")
        self.assertNotIn("Codex", frontend)
        self.assertNotIn("codex_", frontend.replace("codex-blender/v1", ""))
        self.assertIn('bl_idname = "partme_blender.', frontend)
        self.assertNotIn("VIEW3D_PT_partme_blender_session", frontend)
        self.assertIn('bl_category = "PartMe MCP"', panel)

    def test_addon_panel_offers_local_approval(self):
        panel = (ADDON / "panel.py").read_text(encoding="utf-8")
        self.assertIn("partme_blender.approve_request", panel)
        self.assertIn("partme_blender.deny_request", panel)
        self.assertIn("approve_pending", panel)

    def test_public_guides_never_name_the_community_addon_as_ours(self):
        for guide in (ROOT / "docs/getting-started").glob("*.md"):
            body = guide.read_text(encoding="utf-8")
            self.assertNotIn("Codex Blender Connector", body, guide.name)


if __name__ == "__main__":
    unittest.main()
