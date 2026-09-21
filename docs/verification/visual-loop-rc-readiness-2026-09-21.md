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

- Keep Fal optional behind a separate ProviderAdapter and a user-approved cost
  ceiling.
- Run Codex, Claude Code, ZCode and Kimi acceptance on macOS and Windows.
- Complete one reproducible real target-image run from an initial score to
  `>= 8` before claiming production readiness.
