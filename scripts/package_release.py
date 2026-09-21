#!/usr/bin/env python3
"""Build deterministic PartMe Blender MCP release assets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def version() -> str:
    text = (ROOT / "src/partme_blender_mcp/harness/version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("runtime version is missing")
    return match.group(1)


def files_under(root: Path):
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def write_zip(target: Path, entries):
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, name in sorted(entries, key=lambda item: item[1]):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if os.access(source, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, source.read_bytes())


def repository_entries():
    """Runtime archive contents: installable package, client guides, and project metadata.

    Brand artwork is deliberately excluded: it is repository page decoration, not runtime
    payload, and would otherwise add ~6 MB of PNGs to every download.
    """
    roots = (
        ROOT / "src",
        ROOT / "docs/getting-started",
        ROOT / "docs/assets/reference",
    )
    entries = []
    for base in roots:
        for path in files_under(base):
            entries.append((path, path.relative_to(ROOT).as_posix()))
    for name in ("pyproject.toml", "README.md", "README.zh-CN.md", "LICENSE", "NOTICE",
                 "SECURITY.md", "THIRD_PARTY_NOTICES.md"):
        entries.append((ROOT / name, name))
    return entries


def addon_entries():
    """Assembled Blender Add-on layout.

    Blender installs one top-level package, so the Add-on sources and the Harness
    runtime they drive are published as a single ``partme_blender_mcp/`` tree. The
    Harness stays owned by ``src/`` and is copied in here, never duplicated on disk.

    ``__main__.py`` and ``doctor.py`` ride along so the same installed package can also
    be launched as an MCP server (``python -m partme_blender_mcp``) and diagnosed with
    ``doctor --json``; two installs of one package name must not behave differently.
    """
    addon_root = ROOT / "addon/partme_blender_mcp"
    src_root = ROOT / "src/partme_blender_mcp"
    entries = [
        (path, "partme_blender_mcp/" + path.relative_to(addon_root).as_posix())
        for path in files_under(addon_root)
    ]
    entries.extend(
        (path, "partme_blender_mcp/harness/" + path.relative_to(src_root / "harness").as_posix())
        for path in files_under(src_root / "harness")
    )
    for name in ("validate_model_in_blender.py", "__main__.py", "doctor.py"):
        entries.append((src_root / name, f"partme_blender_mcp/{name}"))
    entries.append((ROOT / "vendor/community/blender_mcp_community/__init__.py",
                    "partme_blender_mcp/provider_backend.py"))
    sdk_root = ROOT / "vendor/tencentcloud_sdk"
    entries.extend(
        (path, "partme_blender_mcp/_vendor/" + path.relative_to(sdk_root).as_posix())
        for path in files_under(sdk_root)
    )
    entries.append((ROOT / "THIRD_PARTY_NOTICES.md", "partme_blender_mcp/THIRD_PARTY_NOTICES.md"))
    names = [name for _, name in entries]
    if len(names) != len(set(names)):
        raise RuntimeError("Add-on archive would contain duplicate entries")
    return entries


def write_tar_gz(target: Path, entries):
    with tempfile.NamedTemporaryFile() as raw:
        with tarfile.open(fileobj=raw, mode="w") as archive:
            for source, name in sorted(entries, key=lambda item: item[1]):
                info = archive.gettarinfo(str(source), arcname=name)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with source.open("rb") as stream:
                    archive.addfile(info, stream)
        raw.flush()
        raw.seek(0)
        with target.open("wb") as output, gzip.GzipFile(
            filename="", mode="wb", fileobj=output, mtime=0, compresslevel=9
        ) as compressed:
            compressed.write(raw.read())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build(output: Path) -> list[Path]:
    release_version = version()
    output.mkdir(parents=True, exist_ok=True)

    addon_name = f"partme-blender-mcp-addon-{release_version}.zip"
    runtime_name = f"partme-blender-mcp-runtime-{release_version}.zip"
    mac_name = f"partme-blender-mcp-macos-arm64-{release_version}.tar.gz"
    windows_name = f"partme-blender-mcp-windows-x64-{release_version}.zip"

    addon_entries_list = addon_entries()
    write_zip(output / addon_name, addon_entries_list)
    write_zip(output / runtime_name, repository_entries())

    mac_installer = ROOT / "installers/macos/install_partme_blender_mcp.command"
    platform_common = repository_entries()
    write_tar_gz(output / mac_name, [
        *platform_common,
        (output / runtime_name, runtime_name),
        (output / addon_name, addon_name),
        (mac_installer, mac_installer.name),
        (ROOT / "installers/README-FIRST.txt", "README-FIRST.txt"),
    ])

    windows_installer = ROOT / "installers/windows/install_partme_blender_mcp.bat"
    windows_ps = ROOT / "installers/windows/install_partme_blender_mcp.ps1"
    write_zip(output / windows_name, [
        *platform_common,
        (output / runtime_name, runtime_name),
        (output / addon_name, addon_name),
        (windows_installer, windows_installer.name),
        (windows_ps, windows_ps.name),
        (ROOT / "installers/README-FIRST.txt", "README-FIRST.txt"),
    ])

    manifest = {
        "schemaVersion": "1.0.0",
        "product": "PartMe Blender MCP",
        "version": release_version,
        "commit": git_commit(),
        "mcpProtocol": "2025-06-18",
        "harnessProtocol": "codex-blender/v1",
        "python": "3.11-3.13",
        "blender": "4.2-5.2",
        "status": "prerelease" if "-" in release_version else "release",
        "artifacts": [addon_name, runtime_name, mac_name, windows_name],
    }
    manifest_path = output / "runtime-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"partme-blender-mcp-{release_version}",
        "documentNamespace": f"https://github.com/full-aigc-plugins/blender-mcp/releases/tag/v{release_version}",
        "creationInfo": {"created": "2026-09-15T00:00:00Z", "creators": ["Organization: PartMe.AI"]},
        "packages": [{
            "name": "partme-blender-mcp",
            "SPDXID": "SPDXRef-Package",
            "versionInfo": release_version,
            "downloadLocation": "https://github.com/full-aigc-plugins/blender-mcp",
            "licenseConcluded": "Apache-2.0",
            "licenseDeclared": "Apache-2.0",
            "filesAnalyzed": False,
        }, {
            "name": "mcp",
            "SPDXID": "SPDXRef-MCP-Python-SDK",
            "versionInfo": ">=2.2.0,<3",
            "downloadLocation": "https://pypi.org/project/mcp/",
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "filesAnalyzed": False,
        }, {
            "name": "tencentcloud-sdk-python-ai3d",
            "SPDXID": "SPDXRef-TencentCloud-AI3D-SDK",
            "versionInfo": "3.1.57",
            "downloadLocation": "https://pypi.org/project/tencentcloud-sdk-python-ai3d/3.1.57/",
            "licenseConcluded": "Apache-2.0",
            "licenseDeclared": "Apache-2.0",
            "filesAnalyzed": False,
        }, {
            "name": "tencentcloud-sdk-python-common",
            "SPDXID": "SPDXRef-TencentCloud-Common-SDK",
            "versionInfo": "3.1.57",
            "downloadLocation": "https://pypi.org/project/tencentcloud-sdk-python-common/3.1.57/",
            "licenseConcluded": "Apache-2.0",
            "licenseDeclared": "Apache-2.0",
            "filesAnalyzed": False,
        }],
        "relationships": [{
            "spdxElementId": "SPDXRef-Package",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-MCP-Python-SDK",
        }, {
            "spdxElementId": "SPDXRef-Package",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-TencentCloud-AI3D-SDK",
        }, {
            "spdxElementId": "SPDXRef-TencentCloud-AI3D-SDK",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-TencentCloud-Common-SDK",
        }],
    }
    sbom_path = output / "SBOM.spdx.json"
    sbom_path.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")

    artifacts = [
        output / addon_name,
        output / runtime_name,
        output / mac_name,
        output / windows_name,
        manifest_path,
        sbom_path,
    ]
    sums_path = output / "SHA256SUMS.txt"
    sums_path.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(artifacts)),
        encoding="utf-8",
    )
    return [*artifacts, sums_path]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist")
    args = parser.parse_args(argv)
    for path in build(Path(args.output).resolve()):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
