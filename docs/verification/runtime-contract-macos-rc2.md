# Runtime contract and visual transport verification (`0.7.0-rc.2`)

Date: 2026-09-21
Host: macOS arm64
Blender: 5.2.1 LTS
Scope: isolated temporary Blender configuration; no user project or preferences modified

## Verified release behavior

- The assembled Add-on and standalone Runtime both report `0.7.0-rc.2`.
- The private descriptor reports 181 Harness commands and a SHA-256 capability digest.
- stdio, Streamable HTTP and compatibility SSE expose the same 184-tool MCP catalog
  across four pages.
- All three transports returned a PNG image content block from `scene.screenshot`.
- Streamable HTTP accepted structured object locators for
  `validation.floor_penetration` and `validation.motion_discontinuity`; both checks
  executed in Blender and passed for the fixture cube.
- Missing and invalid remote bearer tokens returned HTTP 401 before MCP processing.
- Two concurrent HTTP clients, one SSE client, disconnect cleanup and HTTP reconnect
  completed successfully.
- Add-on disable and Harness revocation removed the isolated session.

Observed catalog schema digest:

```text
49fd84d355eb16fc520901e6978fecefd2d8bc25fe740a2dc444dbe1bad0ea41
```

Observed Add-on capability digest:

```text
86a5c8cff9ed6f4c60746ae1640ebac7bf1d81840bf18590c1008833de8bf106
```

## Automated evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 252 tests passed, 6 skipped.
- `/opt/anaconda3/bin/ruff check src addon tests scripts`: passed.
- `openspec validate add-visual-loop --strict`: passed.
- `tests/runtime/remote_transport_smoke.py`: passed in packaged Add-on layout.
- `scripts/package_release.py`: produced Add-on, Runtime, macOS arm64 and Windows x64
  prerelease assets; archive inspection confirmed `scene.screenshot` and
  `runtime_contract.py` are present.

## Not claimed by this record

- Windows execution (the archive was built, not run on Windows).
- Native launches from Codex, Claude Code, ZCode and Kimi individually; the protocol
  path was verified with the official MCP Python client.
- A real visual Judge improvement from 0 to at least 8.
- GitHub release publication or installation into the user's active Blender profile.
