# Contributing

Thanks for considering a contribution to PartMe Blender MCP. This project ships a
security boundary between MCP clients and a user's Blender session, so changes are
reviewed against the trust model in
[`docs/superpowers/specs/2026-09-15-partme-blender-mcp-design.md`](docs/superpowers/specs/2026-09-15-partme-blender-mcp-design.md)
as well as for correctness.

## Repository layout

| Path | Owns |
|:---|:---|
| `src/partme_blender_mcp/` | The runtime Python package: stdio MCP server, Harness, command catalog |
| `src/partme_blender_mcp/harness/` | Session security boundary, transport, transactions, Blender version adapters |
| `src/partme_blender_mcp/harness/commands/` | One module per command domain; commands are registered, validated, and closed |
| `addon/partme_blender_mcp/` | The Blender Add-on: `bl_info`, panel, and session lifecycle only |
| `installers/` | macOS and Windows user-scope installers |
| `scripts/package_release.py` | Release assembly, manifest, SBOM, and checksums |
| `tests/` | Standard-library `unittest` suites, runnable without Blender |

Two rules keep the layout honest:

1. **The runtime lives in `src/` and only in `src/`.** The Add-on archive is assembled at
   package time by copying the Harness under the Add-on's single top-level directory. Do
   not copy Harness files into `addon/`; `tests/test_project_structure.py` fails if the
   Add-on tree grows runtime-owned modules.
2. **Identity is defined once, in `harness/version.py`.** The Add-on's top-level
   `__init__.py` belongs to Blender's Add-on loader, so it cannot hold runtime identity;
   `harness/version.py` resolves in both the pip-installed runtime and the installed
   Add-on.

## Development

```bash
python3 -m unittest discover -s tests         # full suite, no Blender required
python3 -m compileall -q src addon scripts    # byte-compile everything shipped
python3 scripts/package_release.py --output dist
```

Blender-side checks run against an isolated configuration so they never touch a user's
open project:

```bash
# Host-neutral MCP client conformance (initialize → paginated tools/list → tools/call → approval)
BLENDER_USER_CONFIG=/tmp/pbm-config BLENDER_USER_SCRIPTS=/tmp/pbm-addons \
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python-exit-code 1 --python tests/runtime/generic_mcp_client_handshake.py \
  -- /path/to/unpacked-addon

# Packaged Add-on install, both panels' operators, approval/deny/rollback/takeover
BLENDER_USER_CONFIG=/tmp/pbm-config BLENDER_USER_SCRIPTS=/tmp/pbm-addons \
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python-exit-code 1 --python tests/runtime/addon_and_approval_smoke.py \
  -- /tmp/pbm-config/../addons
```

## Rules that are enforced by tests

- Every relative Markdown link and image target must exist.
- No guide may contain a developer-machine path, and no document may name the unrelated
  community `MCP for Blender` Add-on as this project's Add-on.
- Public MCP tools use single-underscore `blender_*` names; Harness command ids keep
  their dotted form. Two Harness ids must never map to one MCP name.
- Gated commands (delete, overwrite, final export, expert Python) cannot be approved by
  a generic MCP client. Only local UI, through `Session.approve_pending`, can approve a
  single retry of one request id.
- Session descriptors stay private: no symlinks, `0600` mode, and the token never
  appears in status or tool results.

## Commits

Use conventional prefixes (`feat:`, `fix:`, `docs:`, `security:`, `test:`, `chore:`).
Keep behavior-preserving refactors separate from behavior changes, and state in the
message which evidence you ran.
