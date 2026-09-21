# Visual Loop RC readiness — 2026-09-21

## Scope

This record covers the development-tree implementation for OpenSpec change
`add-visual-loop`: reliable screenshots, target locking, structured verdicts,
stall detection, explicit transaction advice, and cross-machine image content.
It is not a release record and does not claim paid-provider, Windows, or real
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

## Remaining release gates

- Choose and publish a new immutable RC version; do not overwrite `0.6.1`.
- Verify remote CI and release assets, then update the downstream plugin lock.
- Add the `blender-visual-loop` Skill only after the plugin consumes that RC.
- Keep Fal optional behind a separate ProviderAdapter and a user-approved cost
  ceiling.
- Run Codex, Claude Code, ZCode and Kimi acceptance on macOS and Windows.
- Complete one reproducible real target-image run from an initial score to
  `>= 8` before claiming production readiness.
