# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims for
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.1.2...v0.2.0
[0.1.1]: https://github.com/full-aigc-plugins/blender-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/full-aigc-plugins/blender-mcp/releases/tag/v0.1.0
