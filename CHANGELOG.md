# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims for
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-09-21

### Added

- Hyper3D Rodin supports MCP OAuth and API-key authentication, including loopback
  callback handling and Codex, Claude Code, ZCode, Kimi and generic MCP client targets.
- Sketchfab supports API Token and OAuth authorization-code authentication with state
  validation, refresh tokens and a centered browser completion page.
- Tencent Hunyuan 3D supports official Tencent Cloud SDK credentials and a separate
  TokenHub CLI authorization adapter, with extensible capability profiles.
- Professional and rapid Hunyuan task types, provider capability registration and
  release-packaged Tencent Cloud SDK dependencies.

### Changed

- Provider cards expose compact, functional authorization controls while preserving the
  approved four-tab Blender sidebar layout.
- Paid generation still passes through cost disclosure, approval, cancellation,
  authorized directories and transactional import.

### Fixed

- AI model cards keep provider identity, the compact settings affordance and the
  enable control in one header instead of expanding `开/关` and `配置` into stacked,
  full-width buttons in narrow sidebars.
- The Blender service-ready summary uses the packaged green confirmation badge rather
  than falling back to a theme-colored checkbox.

## [0.5.1] - 2026-09-20

### Added

- Provider-specific credential dialogs for PartMe Poly Pizza, Sketchfab, Hyper3D Rodin
  and Tencent Hunyuan 3D, with secrets retained only in Blender user preferences.
- Atomic live execution-policy reconfiguration and visible foreground Blender acceptance
  coverage for normal, generating, failed and local-approval states.
- Packaged green, amber, blue, gray and red status icons plus provider `uiOrder`
  metadata, so future providers keep the confirmed visual hierarchy without renderer edits.

### Changed

- The four workbench tabs now use an always-visible expanded enum row, preserving the
  confirmed V4 layout at narrow N-panel widths where `prop_tabs_enum` hid inactive tabs.
- Provider cards, Work progress, quick-operation icons and automatic generation routing
  now follow the confirmed V4 visual and interaction contract.
- Paid provider operations remain automatic while the cumulative configured budget permits
  them and enter the trusted Blender approval flow before an over-budget operation runs.

### Fixed

- Community provider refresh now reads the in-process Blender service instead of making
  a loopback call that could deadlock Blender's main-thread command queue.
- Missing provider credentials force the switch off and locked; configured native Poly
  Pizza follows its intended enabled-by-default PartMe path.
- Sketchfab status refresh no longer performs a blocking network request from Blender's
  UI thread.

## [0.5.0] - 2026-09-20

### Added

- One Blender-native workbench with Work, Assets, Models and Access tabs, real provider
  switches, task progress/cancellation, directed settings and retained viewport shortcuts.
- Official MCP Python SDK transports for stdio, Streamable HTTP and compatibility SSE,
  with independent remote listener lifecycles and live client counts.
- Protected Bearer Token configuration and strong one-time token generation in the Access
  tab, with rotation blocked while HTTP or SSE listeners are active.
- Guarded staging for generated GLB/GLTF/FBX/OBJ and ZIP results under approved asset
  roots, including archive traversal, symlink, type, file-count and size checks.

### Changed

- Streamable HTTP and SSE share the exact stdio tool catalog, schemas, pagination and
  result semantics instead of maintaining a second hand-written JSON-RPC server.
- Community Sketchfab and Hyper3D downloads resolve locally and stage through PartMe;
  direct community download/import commands remain outside the public MCP allowlist.

### Security

- Non-loopback listeners require bearer authentication, OAuth issuer metadata and an
  HTTPS public URL; listener tokens are accepted only through the environment.
- Signed provider URLs no longer appear in MCP receipts, UI state or copied endpoints.

## [0.4.0] - 2026-09-19

### Added

- Extensible, data-driven Blender panels for asset libraries and AI model providers,
  including normalized status, configuration actions, task progress and cancellation.
- A provider-neutral generation task protocol that survives community-provider polling
  and can recover the UI state after Blender restarts.
- An asset strategy setting with automatic search-and-generation as the default.

### Changed

- The PartMe production panel now follows the approved native Blender layout: connection,
  permissions, providers, generation progress, approvals and quick viewport controls.
- Community provider status is refreshed explicitly and cached; drawing the panel never
  performs network I/O.

### Security

- Provider results continue through approved directories and guarded transactional import.
- Cancelling a provider without a remote cancellation API stops local polling/import and
  explicitly reports that the remote job may continue.

## [0.3.0] - 2026-09-19

### Added

- Unified, secret-free provider catalog/status protocol and generic Blender panels for
  asset libraries and AI model providers.
- Native Poly Pizza search/download, approved provider-result staging, and separate
  transactional import commands.
- A local-approval gate for paid generation and other external provider actions.

### Changed

- Community providers are contributed by the Blender Design plugin; direct community
  download/import commands are excluded from the public bridge.
- Version metadata, package metadata, Add-on metadata, receipts, documentation and
  release artifacts now derive from the same `0.3.0` source.

## [0.2.1] - 2026-09-19

### Added

- Blender N-panel functional zones for connection, approvals, approved directories,
  execution mode and production progress.

## [0.2.0] - 2026-09-19

### Added

- Vendored upstream community Blender Add-on as a separately packaged MIT artifact.

## [0.1.1] - 2026-09-15

### Added

- Local approval surface in Blender for gated commands: the session records each refused
  request and the PartMe MCP panel (both the Add-on tab and the shared session panel)
  can approve or deny it. Approval is bound to one `requestId` + command, expires, and is
  single use, so a generic MCP client still cannot approve its own request.
- Connecting client name and version are recorded at `initialize` and reported by
  `blender_connection_status`.
- The Add-on archive now also carries `__main__.py` and `doctor.py`, so the installed
  Add-on package can serve as the MCP runtime (`python -m partme_blender_mcp`) instead of
  failing with `'partme_blender_mcp' is a package and cannot be directly executed`.
- `tests/test_authorization_approval.py`, `tests/test_project_structure.py`,
  `tests/test_transport_paths.py`, and the `tests/runtime/` scripts for a live Blender
  host (generic MCP client handshake, Add-on and approval smoke).
- `CONTRIBUTING.md`, `CHANGELOG.md`, `.editorconfig`, and a Ruff configuration with a CI
  lint step.

### Changed

- Product identity (`__version__`, product name, protocol identifiers) is defined once in
  `harness/version.py`; the MCP `initialize` response no longer hardcodes a version that
  could drift from the package.
- Gated tool descriptions and the `AUTHORIZATION_REQUIRED` message now explain the local
  approval flow, and a locally denied request id no longer re-prompts the user.
- `validate_model_in_blender.py` moved into the runtime package, where
  `reimport_validator` resolves it. Re-import validation previously failed in every
  runtime-only install because the script lived under `addon/`.
- Unix socket names are derived from a short hash of the session id and the path budget is
  checked, so the documented default runtime directory always fits; an over-long
  `PARTME_BLENDER_RUNTIME_DIR` now reports the setting to change instead of raising
  `OSError: AF_UNIX path too long`.
- Release archives no longer carry ~6 MB of brand artwork; the runtime archive holds the
  package, guides, and project metadata only (6.83 MB → 0.97 MB).

### Fixed

- macOS and Windows platform bundles now place `pyproject.toml` and `src/` at the archive root, so
  an accidental `python -m pip install <platform-bundle>` works instead of reporting that the archive
  is not a Python project. Each bundle also includes `README-FIRST.txt` and the one-click installer.

- The shared argument catalog had three duplicated keys (`points`, `resolution`,
  `targetObjectId`) where a vendor-uploader definition silently overrode the real one.
  `resolution` was published to clients as a string instead of the positive integer that
  `curve.create`/`curve.configure` require, and `points` lost its item schema.
- Dead code removed from the migrated Harness: unused imports and locals, a leftover
  `common_validation` tuple, an ambiguous `l` loop variable, and an unreachable
  `session.authorize` schema branch in the MCP adapter.

## [0.1.0] - 2026-09-15

### Added

- Cross-client stdio MCP runtime (`python -m partme_blender_mcp`) with a read-only
  `doctor --json`, and the **PartMe Blender MCP** Add-on installed from a single ZIP.
- Guarded Harness extracted from `codex-blender-plugin`: 164 vendor-neutral commands
  across 36 domains, closed argument schemas, scene revisions, milestone transactions and
  rollback, background jobs, and verified multi-format exports.
- Session security boundary: private descriptors (`0600`, no symlinks), per-session token,
  Unix domain socket on macOS, Named Pipe on Windows, and action-bound authorization
  claims with a TTL.
- Blender 4.2–5.2 compatibility adapters and prerelease macOS/Windows installers.
- Release pipeline producing the Add-on, runtime, platform bundles, `runtime-manifest.json`,
  `SHA256SUMS.txt`, and an SPDX SBOM; the Add-on, arbitrary `advanced.execute_python`, and
  all vendor uploader commands are excluded from the public MCP catalog.
- Cross-client guides (Codex, Claude Desktop, Claude Code, MiniMax Design, Cursor, generic
  MCP, macOS, Windows) with a documentation contract test.

[Unreleased]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.5.3...v0.6.0
[0.5.3]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.1.2...v0.2.0
[0.1.1]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/full-aigc-plugins/blender-mcp/releases/tag/v0.1.0
