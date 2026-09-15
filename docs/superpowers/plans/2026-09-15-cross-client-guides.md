# Cross-Client Illustrated Guides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish eight detailed Chinese operation manuals for installing and validating PartMe Blender MCP with Codex, Claude Desktop, Claude Code, MiniMax Design, Cursor, generic MCP clients, macOS, and Windows.

**Architecture:** Keep client-specific instructions in separate files under `docs/getting-started/`, backed by one reviewed source registry containing official URLs, commands, asset names, and evidence status. A Python standard-library test validates every Markdown link and image, rejects developer-machine paths, and requires every client guide to distinguish MCP-client setup from Blender Add-on setup.

**Tech Stack:** Markdown, PNG references, Python 3 unittest, official Blender/Anthropic/Cursor/MCP documentation, local Codex CLI help, and user-provided MiniMax Design screenshots.

**Spec:** `docs/superpowers/specs/2026-09-15-partme-blender-mcp-design.md`

## Global Constraints

- Product: `PartMe Blender MCP`; repository: `partme-ai/blender-mcp`.
- Add-on archive: `partme-blender-mcp-addon-<version>.zip`; runtime archive: `partme-blender-mcp-runtime-<version>.zip`.
- MCP Server ID: `partme_blender`; tools: single-underscore `blender_*`.
- GitHub Release is the recommended download source. Before the first Release exists, every guide must show a pre-release warning instead of claiming the download is available.
- Local `stdio` is the only V1 transport commitment.
- MiniMax Design's form and transport choices are evidenced by user screenshots; only `stdio` receives executable setup instructions.
- No guide may contain `/Users/wandl`, a Codex cache path, a fabricated menu, an API key, or instructions to enable the unrelated community `MCP for Blender`.
- Support claims use `VERIFIED`, `DOCUMENTED_NOT_RUN`, or `UNAVAILABLE`.

---

## Execution record (2026-09-15)

All seven tasks are delivered and pushed. Checkbox state above is evidence-backed, not a
claim: each task's named artifact exists and the contract test exits 0.

```text
8 guides + index + sources.json + 4 follow-up manuals (blender-addon, blender-addon.zh-CN,
upgrade.zh-CN, uninstall.zh-CN) all present
python3 -m unittest discover -s tests   -> 56 tests, OK
```

Evidence labels in `sources.json` are unchanged: `codex` is `VERIFIED` for CLI syntax only;
every other client remains `DOCUMENTED_NOT_RUN` because no released version has completed a
live handshake with it yet.

---

### Task 1: Documentation contract and source registry

**Files:**
- Create: `docs/getting-started/sources.json`
- Create: `tests/test_getting_started_docs.py`

**Interfaces:**
- Consumes: product identities and evidence rules from the design spec.
- Produces: reviewed source metadata and reusable assertions for all manuals.

- [x] **Step 1: Write the failing documentation contract tests**

Require the eight requested files. Parse relative Markdown images/links, reject missing targets and `/Users/wandl`, require both archive names, and require every client guide to contain `PartMe Blender MCP`, `partme_blender`, `blender_connection_status`, `blender_scene_inspect`, an evidence label, and links to both platform manuals.

- [x] **Step 2: Run the test and verify it fails for missing manuals**

```bash
python3 -m unittest tests.test_getting_started_docs
```

Expected: FAIL listing the eight absent Markdown files.

- [x] **Step 3: Add `sources.json`**

Record official Blender download/manual links, MCP 2025-06-18, local `codex mcp add --help`, Anthropic Claude Desktop/Code sources, Cursor's MCP source, and MiniMax screenshot provenance. Record observed versus runtime-verified status separately.

- [x] **Step 4: Run source tests**

```bash
python3 -m unittest tests.test_getting_started_docs.SourceRegistryTests
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add docs/getting-started/sources.json tests/test_getting_started_docs.py
git commit -m "test: define cross-client documentation contract"
```

### Task 2: macOS and Windows manuals

**Files:**
- Create: `docs/getting-started/macos.zh-CN.md`
- Create: `docs/getting-started/windows.zh-CN.md`

**Interfaces:**
- Consumes: release identities, Blender references, and platform paths.
- Produces: platform prerequisites linked by every client guide.

- [x] **Step 1: Write the macOS manual**

Cover Apple Silicon/Intel selection, official Blender download, `shasum -a 256`, Python detection, runtime extraction, Blender From Disk installation using the supplied screenshots, `N → PartMe MCP → Start MCP Server`, Gatekeeper-safe troubleshooting, upgrade, uninstall, and read-only verification.

- [x] **Step 2: Write the Windows manual**

Cover official Blender installer, `py -3 --version`, `Get-FileHash -Algorithm SHA256`, paths with spaces, runtime extraction, Add-on installation, Named Pipe behavior, Windows Defender guidance without opening a public firewall port, upgrade, uninstall, and `DOCUMENTED_NOT_RUN` status.

- [x] **Step 3: Validate**

```bash
python3 -m unittest tests.test_getting_started_docs.PlatformGuideTests
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add docs/getting-started/macos.zh-CN.md docs/getting-started/windows.zh-CN.md
git commit -m "docs: add macOS and Windows installation manuals"
```

### Task 3: Codex manual

**Files:**
- Create: `docs/getting-started/codex.zh-CN.md`

**Interfaces:**
- Consumes: current local Codex CLI syntax and platform manuals.
- Produces: Codex plugin-managed and standalone stdio setup.

- [x] **Step 1: Write the guide**

Use:

```bash
codex mcp add partme_blender -- python -m partme_blender_mcp
codex mcp list
codex mcp get partme_blender
```

Explain runtime prerequisites, new-task refresh, independent Blender Add-on connection, read-only smoke, removal, and the difference between Codex plugin installation and standalone MCP registration.

- [x] **Step 2: Validate**

```bash
python3 -m unittest tests.test_getting_started_docs.CodexGuideTests
```

Expected: PASS and no cache-specific path.

- [x] **Step 3: Commit**

```bash
git add docs/getting-started/codex.zh-CN.md
git commit -m "docs: add Codex MCP operation manual"
```

### Task 4: Claude Desktop and Claude Code manuals

**Files:**
- Create: `docs/getting-started/claude-desktop.zh-CN.md`
- Create: `docs/getting-started/claude-code.zh-CN.md`

**Interfaces:**
- Consumes: Anthropic's current DXT/local MCP and Claude Code MCP documentation.
- Produces: distinct GUI and CLI paths.

- [x] **Step 1: Write Claude Desktop**

Prefer a future `.dxt` artifact and mark it pre-release. Document Settings → Extensions → Advanced settings → Install Extension. Explain that remote Connectors are not the local stdio path. Include restart, tool visibility, approval, logs, disable, and uninstall.

- [x] **Step 2: Write Claude Code**

Use:

```bash
claude mcp add --transport stdio --scope user partme_blender -- python -m partme_blender_mcp
claude mcp list
```

Document option ordering, the `--` separator, scopes, `/mcp`, project approval, removal, and Blender smoke.

- [x] **Step 3: Validate and commit**

```bash
python3 -m unittest tests.test_getting_started_docs.ClaudeGuideTests
git add docs/getting-started/claude-desktop.zh-CN.md docs/getting-started/claude-code.zh-CN.md
git commit -m "docs: add Claude MCP operation manuals"
```

### Task 5: MiniMax Design manual

**Files:**
- Create: `docs/getting-started/minimax-design.zh-CN.md`

**Interfaces:**
- Consumes: both user-provided MiniMax screenshots and platform runtime commands.
- Produces: screenshot-led stdio configuration with explicit evidence limits.

- [x] **Step 1: Write the manual**

Show both screenshots. Use connector name `partme_blender`, type `stdio`, command `python`, arguments `-m partme_blender_mcp`, and enable-after-add. Explain absolute Python paths. Describe the observed HTTP, Streamable HTTP, and SSE choices but mark them unsupported in V1. Do not invent advanced-option content. Mark runtime status `DOCUMENTED_NOT_RUN`.

- [x] **Step 2: Validate and commit**

```bash
python3 -m unittest tests.test_getting_started_docs.MiniMaxGuideTests
git add docs/getting-started/minimax-design.zh-CN.md
git commit -m "docs: add MiniMax Design MCP manual"
```

### Task 6: Cursor and generic MCP manuals

**Files:**
- Create: `docs/getting-started/cursor.zh-CN.md`
- Create: `docs/getting-started/generic-mcp.zh-CN.md`

**Interfaces:**
- Consumes: Cursor's official `mcp.json` locations and MCP 2025-06-18.
- Produces: Cursor global/project examples and a host-neutral stdio contract.

- [x] **Step 1: Write Cursor**

Use `~/.cursor/mcp.json` and `.cursor/mcp.json` with:

```json
{"mcpServers":{"partme_blender":{"command":"python","args":["-m","partme_blender_mcp"]}}}
```

Explain scope, tool approval, refresh, `cursor-agent mcp list`, `cursor-agent mcp list-tools partme_blender`, and Blender smoke.

- [x] **Step 2: Write generic MCP**

Document stdout-only JSON-RPC, stderr logging, initialize negotiation, initialized notification, paginated tools/list, tools/call, shutdown, environment inheritance, working-directory independence, and generic JSON configuration. Require clients to follow `nextCursor` and never treat annotations as authorization.

- [x] **Step 3: Validate and commit**

```bash
python3 -m unittest tests.test_getting_started_docs.CursorAndGenericGuideTests
git add docs/getting-started/cursor.zh-CN.md docs/getting-started/generic-mcp.zh-CN.md
git commit -m "docs: add Cursor and generic MCP manuals"
```

### Task 7: Navigation and final evidence

**Files:**
- Create: `docs/getting-started/README.zh-CN.md`
- Modify: all eight manuals as required by link validation.
- Modify: `docs/assets/reference/README.md`

**Interfaces:**
- Consumes: all manuals and references.
- Produces: a user-facing decision table and reproducible documentation gate.

- [x] **Step 1: Add the index**

Put Blender Add-on installation before MCP client configuration. Show platform/client evidence separately.

- [x] **Step 2: Run complete validation**

```bash
python3 -m unittest tests.test_getting_started_docs
git diff --check
rg -n '/Users/wandl|codex-blender-connector|blender__' docs/getting-started
```

Expected: tests and diff check PASS; `rg` returns no matches.

- [x] **Step 3: Commit**

```bash
git add docs/getting-started docs/assets/reference/README.md tests/test_getting_started_docs.py
git commit -m "docs: complete cross-client Blender MCP manuals"
```

- [x] **Step 4: Publish only when authorized**

```bash
git push origin main
```

This pushes documentation only. It does not create a GitHub Release or claim an unavailable runtime.
