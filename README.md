# PartMe Blender MCP

> One secure, visible, recoverable Blender MCP runtime for Codex, Claude, MiniMax Design, Cursor, and other MCP clients.

<p align="center"><img src="assets/brand/logo.png" alt="PartMe Blender MCP" width="144"></p>

[English](README.md) | [简体中文](README.zh-CN.md) · [Setup guides](docs/getting-started/README.zh-CN.md) · [Security](SECURITY.md) · [Architecture](docs/superpowers/specs/2026-09-15-partme-blender-mcp-design.md)

![PartMe Blender MCP Hero](assets/brand/hero.png)

## Positioning

PartMe Blender MCP translates standard MCP `stdio` requests into Blender operations guarded by closed schemas, transactions, scene revisions, path policy, local authorization, snapshots, and recovery. It is not a text-to-3D model and is not tied to one AI client.

### Who it is for

- Creators who want natural-language Blender control while keeping the foreground UI and manual takeover.
- Teams that want Codex, Claude, MiniMax Design, or Cursor to share one Blender integration.
- Automation engineers who require structured tools, rollback, verified exports, and explicit trust boundaries.

### Problems solved

| Problem | PartMe Blender MCP | Evidence entry |
|:---|:---|:---|
| A different Blender plugin per client | One neutral Add-on and MCP runtime | `partme_blender` |
| Arbitrary Python is hard to audit | 164 closed Blender commands; expert Python is not exposed | `blender_capability_list` |
| Human edits can be overwritten | `sceneRevision`, transactions, takeover invalidation | `blender_connection_status` |
| Export failure loses context | Snapshots, rollback, background jobs, receipts | `blender_job_status` |
| Setup is fragmented | Separate platform and client guides | [Setup center](docs/getting-started/README.zh-CN.md) |

## At a glance

```text
Codex / Claude / MiniMax Design / Cursor / Generic MCP
                         │  MCP 2025-06-18 · stdio
                         ▼
┌────────────────────────────────────────────────────────┐
│ PartMe Blender MCP                                     │
│ 1. MCP lifecycle and paginated tool catalog            │
│ 2. Private token, closed schema, transaction, revision │
│ 3. Blender main-thread execution and manual takeover   │
│ 4. Modeling, animation, rendering, video, delivery     │
└────────────────────────────────────────────────────────┘
                         │ private UDS / Named Pipe
                         ▼
             Foreground Blender + PartMe MCP Add-on
```

![PartMe Blender MCP architecture](assets/brand/architecture.png)

| Property | Value |
|:---|:---|
| Product | PartMe Blender MCP |
| MCP server ID | `partme_blender` |
| Version | `0.1.0` prerelease |
| MCP protocol | `2025-06-18` |
| Harness compatibility | `codex-blender/v1` |
| Blender | 4.2–5.2, only as verified per matrix |
| Python | 3.11–3.13 |
| Transport | stdio to macOS UDS / Windows Named Pipe |
| License | Apache-2.0 |

## Capabilities and boundaries

### Implemented surface

| Domain | Capabilities | Current evidence |
|:---|:---|:---|
| Scene and modeling | Objects, collections, mesh, curves, modifiers, hard-surface recipes | Migrated from the proven Harness; new-repo Blender regression pending |
| UV and look development | UV, PBR materials, textures, Geometry Nodes, baking | Same |
| Character and animation | Armatures, weights, constraints, IK/FK, Actions, F-Curves, NLA, shape keys | Same |
| Camera and rendering | Camera paths, handheld response, Eevee/Cycles, passes, compositor | Same |
| Simulation and editors | Rigid body, cloth, soft body, smoke, Grease Pencil, tracking, VSE | Same |
| Quality and delivery | Geometry/motion/camera checks, snapshots, jobs, multi-format export | Same |
| MCP | initialize, paginated tools/list, tools/call, structuredContent | Automated tests |

### Out of scope

- Story writing, production planning, or multi-shot orchestration.
- Bundled Rodin, Hunyuan, Dreamina, Sketchfab, or other vendor services.
- Silent Blender, extension, asset, or model downloads.
- Treating a successful connection as artistic acceptance.
- Production claims for untested client/platform combinations.

## Installation

### 1. Install Blender

Download Blender from the [official website](https://www.blender.org/download/) and launch it once.

### 2. Download the release

Download from [v0.1.0](https://github.com/partme-ai/blender-mcp/releases/tag/v0.1.0):

```text
partme-blender-mcp-addon-0.1.0.zip
partme-blender-mcp-runtime-0.1.0.zip
SHA256SUMS.txt
```

Verify SHA-256 before installing.

### 3. Install the runtime

```bash
python -m pip install ./partme-blender-mcp-runtime-0.1.0.zip
python -m partme_blender_mcp --help
```

Platform packages also contain `install_partme_blender_mcp.command` for macOS and `install_partme_blender_mcp.bat` for Windows.

### 4. Install the Blender Add-on

1. Blender → **Edit → Preferences → Add-ons**.
2. Top-right menu → **Install from Disk…**.
3. Select `partme-blender-mcp-addon-0.1.0.zip` without extracting it.
4. Enable **PartMe Blender MCP**.
5. Return to 3D View, press `N`, open **PartMe MCP**.
6. Choose approved directories and click **Start MCP Server**.

![Install from Disk](docs/assets/reference/blender-install-from-disk.png)

### 5. Configure a client

| Client | Guide |
|:---|:---|
| Codex | [Codex](docs/getting-started/codex.zh-CN.md) |
| Claude Desktop | [Claude Desktop](docs/getting-started/claude-desktop.zh-CN.md) |
| Claude Code | [Claude Code](docs/getting-started/claude-code.zh-CN.md) |
| MiniMax Design | [MiniMax Design](docs/getting-started/minimax-design.zh-CN.md) |
| Cursor | [Cursor](docs/getting-started/cursor.zh-CN.md) |
| Generic MCP | [Generic MCP](docs/getting-started/generic-mcp.zh-CN.md) |
| macOS | [macOS](docs/getting-started/macos.zh-CN.md) |
| Windows | [Windows](docs/getting-started/windows.zh-CN.md) |

## Quick start

```json
{
  "mcpServers": {
    "partme_blender": {
      "command": "python",
      "args": ["-m", "partme_blender_mcp"]
    }
  }
}
```

Start a new client conversation and call:

```text
blender_connection_status
blender_scene_inspect
```

Only proceed to mutations after both read-only checks succeed. Mutations use transactions; destructive operations still require local authorization.

## Security and recovery

- Descriptors reject symlinks and broad permissions; tokens never enter MCP results.
- macOS uses a private Unix Domain Socket; Windows uses a user-scoped Named Pipe.
- Mutations carry the current `sceneRevision`.
- One Blender session has one active writer by default.
- Pause, Take Over, and Revoke invalidate old transactions and claims.
- In `v0.1.0`, delete, overwrite, expert Python, and gated final export return `AUTHORIZATION_REQUIRED`; no generic MCP tool can mint approval.
- Tool `annotations` are hints; the Harness is authoritative.

Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/partme-ai/blender-mcp/security/advisories/new).

## Errors and troubleshooting

| Error | Meaning | Action |
|:---|:---|:---|
| `BLENDER_NOT_CONNECTED` | No live Harness | Click Start MCP Server in Blender |
| `AMBIGUOUS_SESSION` | Multiple Blender sessions | Bind the intended window |
| `STALE_SCENE_REVISION` | Scene changed | Reinspect and start a new transaction |
| `AUTHORIZATION_REQUIRED` | No trusted approval | Stop in `v0.1.0`; clients cannot self-assert confirmation |
| Incomplete tools | Pagination not followed | Continue with `nextCursor` |

## Development, verification, and release

```bash
python -m unittest discover -s tests
python -m compileall -q src addon scripts tests
python -m ruff check src addon scripts tests
python scripts/package_release.py --output dist
git diff --check
```

Release output includes the Add-on, runtime, macOS/Windows bundles, `runtime-manifest.json`, `SHA256SUMS.txt`, and `SBOM.spdx.json`. Tags matching `v*` trigger the prerelease workflow.

The host-neutral MCP conformance run needs Blender and a live session:

```bash
BLENDER_USER_CONFIG=/tmp/pbm-config BLENDER_USER_SCRIPTS=/tmp/pbm-addons \
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python-exit-code 1 --python tests/runtime/generic_mcp_client_handshake.py \
  -- /path/to/unpacked-addon
```

## Repository map

```text
blender-mcp/
├── src/partme_blender_mcp/            # stdio MCP runtime, CLI, and doctor
│   └── harness/                       # session boundary, transport, commands, compat
│       ├── commands/                  # one module per command domain
│       ├── compat/                    # Blender 4.2 → 5.2 adapters
│       └── version.py                 # single source of product identity
├── addon/partme_blender_mcp/          # Blender Add-on: bl_info, panel, lifecycle only
├── installers/                        # macOS and Windows user-scope installers
├── scripts/package_release.py         # reproducible release builder
├── tests/                             # docs, approval, structure, release contracts
│   └── runtime/                       # scripts that need a live Blender session
├── docs/getting-started/              # illustrated client/platform guides
├── docs/verification/                 # security, license, and handshake evidence
├── assets/brand/                      # logo, hero, cover, architecture
└── dist/                              # build output (not tracked)
```

The runtime lives in `src/` only. The Add-on archive is assembled at package time: the
Harness is copied under the Add-on's single top-level directory, so `partme_blender_mcp`
installs as one package from either archive. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Compatibility and migration

`0.1.0` is a prerelease. The Harness keeps `codex-blender/v1` temporarily for differential migration from `codex-blender-plugin`; all public identity, MCP server ID, and Add-on surfaces use PartMe. Untested clients remain `DOCUMENTED_NOT_RUN`.

## Deep documentation

- [Cross-client architecture](docs/superpowers/specs/2026-09-15-partme-blender-mcp-design.md)
- [Illustrated setup center](docs/getting-started/README.zh-CN.md)
- [v0.1.0 security review](docs/verification/security-review-0.1.0.md)
- [v0.1.0 license compliance triage](docs/verification/license-compliance-0.1.0.md)
- [Generic MCP client handshake evidence](docs/verification/generic-mcp-handshake-2026-09-15.md)
- [Brand assets and generation provenance](assets/brand/README.md)

## Contributing and license

Changes must include corresponding tests and compatibility evidence. Do not expand default permissions or mix vendor integrations into the core.

Licensed under [Apache-2.0](LICENSE).
