# Visual Loop RC readiness — 2026-09-21

## Scope

This record covers the implementation and RC publication for OpenSpec change
`add-visual-loop`: reliable screenshots, target locking, structured verdicts,
stall detection, explicit transaction advice, cross-machine image content, and
the downstream orchestration Skill. It does not claim paid-provider or real
target-image score acceptance.

## Automated evidence

- Python 3.13 full unit suite: `245` tests passed.
- Ruff: all `src`, `addon`, `scripts`, and `tests` checks passed.
- `compileall`: passed for `src`, `addon`, `scripts`, and `tests`.
- `openspec validate add-visual-loop --strict`: passed.
- `git diff --check`: passed.
- Candidate Add-on archive contains:
  - `partme_blender_mcp/harness/image_artifact.py`
  - `partme_blender_mcp/harness/scene_screenshot.py`
  - `partme_blender_mcp/harness/visual_loop.py`

## Real Blender evidence

Blender `5.2.1 LTS` was launched with isolated `BLENDER_USER_CONFIG` and
`BLENDER_USER_SCRIPTS`; no user profile or open project was used.

`native_visual_loop_smoke.py` verified:

- successful 64x48 PNG screenshot;
- camera, frame and render-setting restoration after success;
- restoration and partial-file cleanup after a real “Cannot render, no camera” failure;
- target copy and SHA-256 lock through a fresh `VisualLoopStore` instance;
- zero network and paid-provider calls.

The produced target SHA-256 was
`fa415dd77a1ac7e50c884ec32fa2d9f5a06f7542ef1a45f49a5a332f5d172655`.

## Real transport evidence

`remote_transport_smoke.py` ran against the assembled Add-on and the pinned
official MCP SDK from Python 3.13. It verified:

- stdio, Streamable HTTP, SSE and HTTP reconnect all exposed the same `184`
  unique tools over `4` pages;
- the common schema digest was
  `0264eb12f08c528f331f9850ba3b3904b26aa09037a9471b9c08d847ca674901`;
- each transport called `blender_scene_screenshot` and received exactly one
  non-empty `image/png` content block;
- two concurrent HTTP clients and one SSE client were visible;
- missing and invalid HTTP/SSE bearer tokens returned `401`;
- stopping HTTP did not stop SSE, and HTTP reconnect succeeded;
- scene revision remained `0` after screenshots.

The first real run exposed that the fixed MCP low-level `Server` no longer has
`streamable_http_app()`. The runtime now composes the official
`StreamableHTTPSessionManager` explicitly; the complete transport run above is
the regression evidence for that correction.

## RC and downstream evidence

- Runtime commit: `f27d1832fab580df2c530cfb15c8f3bfad88a2f1`.
- Immutable prerelease: [`v0.7.0-rc.1`](https://github.com/full-aigc-plugins/blender-mcp/releases/tag/v0.7.0-rc.1).
- Runtime CI run `35585800217` passed on Ubuntu, macOS, and Windows; release run
  `35586048128` completed successfully.
- Freshly downloaded Release assets passed `SHA256SUMS.txt`; the Add-on digest
  is `9ffc63ebf4db3771d5a2fd320063b4245a15a614fc296557ba9218ea96b10522`
  and the Runtime digest is
  `c85a8e2a8a288350bf8a71b3139ec96497d8b77f4260a62e87fdecb9aa836d01`.
- Blender Design [`v0.13.0`](https://github.com/full-aigc-plugins/blender-design-plugin/releases/tag/v0.13.0)
  pins those exact artifacts and ships `blender-visual-loop` with both
  subagent-judge and single-agent orchestration strategies.
- Downstream PR `#4` passed distribution, vendored-skill, and Blender 4.2.23,
  4.5.13, and 5.2.1 certification on macOS and Windows before merge.
- The public plugin catalog pins Blender Design `0.13.0` at `v0.13.0`.

## Remaining release gates

- Run Codex, Claude Code, ZCode and Kimi acceptance on macOS and Windows.
- Complete one reproducible real target-image run from an initial score to
  `>= 8` before claiming production readiness.

## Fal decision

Task 4.3 is complete as a negative integration decision. The visual loop is a
deterministic state machine and does not call a visual model itself; verdicts
come from a human or client-side Judge. Therefore this RC does not need Fal and
must not add a paid dependency merely to close the checklist. If a later change
requires Fal, it remains a separate `ProviderAdapter` with an explicit cost
ceiling, uncertain-submit recovery, polling, and remote cancellation semantics.

## Client acceptance in progress

The first real Codex run exposed a downstream distribution defect rather than a
runtime transport defect: Blender Design `0.13.0` declared `python` as its MCP
command, but the macOS acceptance host only exposed `python3`. Blender Design
`0.13.1` now launches a cross-platform Node shim which discovers Python
3.11-3.13 (`python3.x`/`python3`/`python` on macOS and Linux, `py -3.x` on
Windows), honors `PARTME_BLENDER_MCP_PYTHON`, and recovers dead bootstrap lock
owners. Its 508-test suite, distribution validator, remote CI, release tag, and
marketplace update all passed.

- Plugin release: [`v0.13.1`](https://github.com/full-aigc-plugins/blender-design-plugin/releases/tag/v0.13.1), commit `e38836eefd418178a8f280ead5f1497037d141c7`.
- Plugin CI: run `35594750496` passed; Skills check run `35594750509` passed.
- Marketplace commit: `4929bcc` pins Blender Design `0.13.1` at `v0.13.1`.

After refreshing the Codex marketplace and cache, a real Codex CLI session used
the installed `0.13.1+codex.20260921` plugin to call
`blender_connection_status` against isolated Blender 5.2.1. The structured
result reported `connected: true`, `sceneRevision: 0`, and `transport: unix`.
The run used an isolated MCP configuration because the user's global Codex
profile currently contains unrelated failing remote servers and more Skills
than the client context budget permits. An explicit
`PARTME_BLENDER_DESCRIPTOR` selected the isolated acceptance Blender because
another user Blender session was also active.

Claude Code `2.1.273` then loaded the same installed launcher through a strict,
single-server MCP configuration. With the only allowed tool restricted to
`blender_connection_status`, the real client call also returned
`status: connected`, `sceneRevision: 0`, and `transport: unix`. The first
attempt under `dontAsk` was correctly denied by Claude's permission system; the
acceptance rerun used non-interactive permission mode while still exposing only
that one read-only tool.

This is macOS Codex and Claude Code evidence only. ZCode, Kimi, Windows, and the
real target-image score run remain open, so task 4.4 is not checked.

Kimi Code `0.43.1` was then started with an isolated `KIMI_CODE_HOME`, the same
`0.13.1` launcher, and only the PartMe MCP declaration. The client stopped
before model/tool execution with its account-level five-hour usage quota
exhausted. This is a client-account blocker, not a successful or failed Blender
MCP call.

ZCode `3.14.1` is installed as a desktop application but has no standalone
`zcode` CLI in `PATH`. Its installed plugin registry still pins Blender Design
`0.12.0`. The live application was already running an unrelated user task, so
the acceptance did not mutate or restart it merely to force a plugin refresh.
ZCode therefore remains unverified until that task is clear and the client has
updated Blender Design to `0.13.1`.
