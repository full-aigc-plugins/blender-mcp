# v0.1.1 Platform Package Installation Evidence

> Date: 2026-09-15  
> Root cause addressed: the v0.1.0 macOS outer bundle was a container, not a Python project.

## Regression

The reported command failed on v0.1.0 because the archive root contained a nested runtime ZIP and installer but no `pyproject.toml`:

```text
ERROR: ... does not appear to be a Python project:
neither 'setup.py' nor 'pyproject.toml' found.
```

v0.1.1 places the installable project at the root of both platform bundles while retaining
`README-FIRST.txt`, the one-click installer, runtime ZIP, and Blender Add-on ZIP.

## Verified commands

```bash
python3.13 -m pip install --no-deps --no-build-isolation   partme-blender-mcp-macos-arm64-0.1.1.tar.gz
python3.13 -m pip install --no-deps --no-build-isolation   partme-blender-mcp-windows-x64-0.1.1.zip
python3.13 -m partme_blender_mcp --version
```

Observed for both installs:

```text
PartMe Blender MCP 0.1.1
```

The macOS one-click installer also passed `--dry-run`. A packaged Add-on was exercised in Blender
5.2.1. The generic stdio client completed initialize, four-page tool discovery, transaction-backed
creation, gated refusal without side effect, Blender-local one-time approval, same-request retry,
deletion, and rollback restoration.

Windows Python 3.13 CI builds and tests the bundle. Windows GUI execution remains separately scoped.

