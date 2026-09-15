#!/usr/bin/env python3
"""Build deterministic PartMe Blender MCP v0.1.0 release assets."""

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
    text = (ROOT / "src/partme_blender_mcp/__init__.py").read_text(encoding="utf-8")
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
    roots = (
        ROOT / "src",
        ROOT / "docs/getting-started",
        ROOT / "docs/assets/reference",
        ROOT / "assets/brand",
    )
    entries = []
    for base in roots:
        for path in files_under(base):
            entries.append((path, path.relative_to(ROOT).as_posix()))
    for name in ("pyproject.toml", "README.md", "README.zh-CN.md", "LICENSE", "NOTICE",
                 "SECURITY.md", "THIRD_PARTY_NOTICES.md"):
        entries.append((ROOT / name, name))
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

    addon_entries = [
        (path, "partme_blender_mcp/" + path.relative_to(ROOT / "addon/partme_blender_mcp").as_posix())
        for path in files_under(ROOT / "addon/partme_blender_mcp")
    ]
    addon_entries.extend(
        (path, "partme_blender_mcp/harness/" + path.relative_to(ROOT / "src/partme_blender_mcp/harness").as_posix())
        for path in files_under(ROOT / "src/partme_blender_mcp/harness")
    )
    write_zip(output / addon_name, addon_entries)
    write_zip(output / runtime_name, repository_entries())

    mac_installer = ROOT / "installers/macos/install_partme_blender_mcp.command"
    write_tar_gz(output / mac_name, [
        (output / runtime_name, runtime_name),
        (output / addon_name, addon_name),
        (mac_installer, mac_installer.name),
        (ROOT / "LICENSE", "LICENSE"),
    ])

    windows_installer = ROOT / "installers/windows/install_partme_blender_mcp.bat"
    windows_ps = ROOT / "installers/windows/install_partme_blender_mcp.ps1"
    write_zip(output / windows_name, [
        (output / runtime_name, runtime_name),
        (output / addon_name, addon_name),
        (windows_installer, windows_installer.name),
        (windows_ps, windows_ps.name),
        (ROOT / "LICENSE", "LICENSE"),
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
        "status": "prerelease",
        "artifacts": [addon_name, runtime_name, mac_name, windows_name],
    }
    manifest_path = output / "runtime-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"partme-blender-mcp-{release_version}",
        "documentNamespace": f"https://github.com/partme-ai/blender-mcp/releases/tag/v{release_version}",
        "creationInfo": {"created": "2026-09-15T00:00:00Z", "creators": ["Organization: PartMe.AI"]},
        "packages": [{
            "name": "partme-blender-mcp",
            "SPDXID": "SPDXRef-Package",
            "versionInfo": release_version,
            "downloadLocation": "https://github.com/partme-ai/blender-mcp",
            "licenseConcluded": "Apache-2.0",
            "licenseDeclared": "Apache-2.0",
            "filesAnalyzed": False,
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
