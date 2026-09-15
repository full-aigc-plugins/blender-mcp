# Generic MCP client handshake — 2026-09-15

> Environment: macOS arm64 (Darwin 25.6.0), Blender 5.2.1 LTS (build `9e2066aef7ef`, 2026-08-25), Python 3.13
> Harness: `partme-blender-mcp-addon-0.1.1.zip` unpacked exactly as a user installs it
> Client: `tests/runtime/generic_mcp_client_handshake.py` — a plain stdio JSON-RPC client, no vendor SDK
> Result: **PASS** on the paths below; Windows and the remaining clients stay `DOCUMENTED_NOT_RUN`

## Why this run exists

The Codex path was already exercised through the plugin's own MCP server. This run proves the
**host-neutral** path: a client that knows nothing about PartMe connects over stdio, negotiates
MCP `2025-06-18`, walks the paginated catalog, writes through a milestone transaction, is refused
on a gated command, and only succeeds after a local approval in Blender.

## Command

```bash
BLENDER_USER_CONFIG=/tmp/pbm-config BLENDER_USER_SCRIPTS=/tmp/pbm-addons \
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python-exit-code 1 --python tests/runtime/generic_mcp_client_handshake.py \
  -- /tmp/addon-extract            # directory containing partme_blender_mcp/
```

The script starts a live Harness inside Blender, launches `python -m partme_blender_mcp` as a
child process, and pumps Blender's main-thread queue while the child talks to the socket.

## Observed report

```json
{
  "protocolVersion": "2025-06-18",
  "serverInfo": {"name": "partme-blender-mcp", "title": "PartMe Blender MCP", "version": "0.1.1"},
  "serverCapabilities": ["tools"],
  "connectionStatus": {
    "connected": true,
    "sessionId": "handshake",
    "client": {"name": "generic-handshake-probe", "version": "1.0"}
  },
  "toolPages": 4,
  "toolCount": 169,
  "doubleUnderscoreNames": [],
  "sceneObjectsBefore": ["Camera", "Cube", "Light"],
  "transactionBegin": "succeeded",
  "createIsError": false,
  "createChangedObjects": ["HandshakeProbe"],
  "probePresentAfterCreate": true,
  "transactionCommit": "succeeded",
  "gatedTransactionBegin": "succeeded",
  "gatedIsError": true,
  "gatedErrorCode": "AUTHORIZATION_REQUIRED",
  "probePresentAfterRefusal": true,
  "hostApproved": {"requestId": "gated-1", "command": "object.delete", "ttlSeconds": 120},
  "gatedRetryIsError": false,
  "gatedRetryStatus": "succeeded",
  "gatedRetryErrorCode": null,
  "probePresentAfterDelete": false,
  "transactionRollback": "succeeded",
  "probePresentAfterRollback": true,
  "sessionPendingAuthorizations": 0,
  "clientExitCode": 0
}
```

## What each observation establishes

| Observation | Meaning |
|:---|:---|
| `protocolVersion` + `serverInfo` | The server negotiates MCP `2025-06-18` and reports the version from `harness/version.py`, not a hardcoded literal. |
| `connectionStatus.client` | `clientInfo` from `initialize` is recorded and reported back to the caller. |
| `toolPages: 4` / `toolCount: 169` | `tools/list` pagination works: the client followed `nextCursor` to exhaustion and saw all 169 tools (2 static + 3 control + 164 commands). |
| `doubleUnderscoreNames: []` | No legacy double-underscore tool name is published. |
| `probePresentAfterCreate: true` | A real write reached Blender through a transaction. |
| `gatedErrorCode: AUTHORIZATION_REQUIRED` with `probePresentAfterRefusal: true` | The gated command was refused **and had no side effect**: the object survived. |
| `hostApproved` + `gatedRetryStatus: succeeded` + `probePresentAfterDelete: false` | After the Blender-side approval of that exact request id, the client's retry of the same request id succeeded and the deletion really happened. No approval value was ever sent to the client. |
| `transactionRollback: succeeded` + `probePresentAfterRollback: true` | Rollback restored the deleted object, so destructiveness is bounded by the milestone transaction. |
| `sessionPendingAuthorizations: 0` | The approval was consumed; it cannot be replayed. |
| `clientExitCode: 0` | Closing stdin ends the stdio server cleanly. |

## Not covered here

- **Windows**: Named Pipe transport, the PowerShell installer, and the Add-on inside a Windows Blender are untested and remain `DOCUMENTED_NOT_RUN`.
- **GUI surfaces**: the Add-on panel and session panel are exercised as code (registration plus the approval operators), not as pixels; this run is headless, so no panel was drawn.
- **Claude Desktop, Claude Code, Cursor, MiniMax Design**: each still needs its own documented handshake against a released version. Their guides remain `DOCUMENTED_NOT_RUN`.
- **Codex**: verified separately through the plugin-managed MCP server, not by this script.

## Companion run: packaged Add-on and both local approval surfaces

`tests/runtime/addon_and_approval_smoke.py` installs the **packaged Add-on ZIP** into an
isolated Blender configuration, enables it exactly as a user does, starts a session from the
Add-on, and registers the shared session panel at the same time — in a GUI both panels
coexist, so their operator ids must not collide. Observed:

```json
{
  "addonDiscovered": true,
  "addonEnabled": true,
  "addonPanelRegistered": true,
  "sessionPanelRegistered": true,
  "approvalOperators": ["approve_pending", "approve_request", "deny_pending", "deny_request"],
  "descriptorMode": "0o600",
  "descriptorRemoved": true,
  "sessionStarted": true,
  "probeCreated": true,
  "deleteRefused": "AUTHORIZATION_REQUIRED",
  "pendingListed": ["ui-1"],
  "probeSurvivesRefusal": true,
  "addonApproveResult": ["FINISHED"],
  "deleteAfterApproval": "succeeded",
  "probeDeleted": true,
  "pendingAfterApproval": 0,
  "rollbackGated": "succeeded",
  "probeRestoredByRollback": true,
  "denyRefused": "AUTHORIZATION_REQUIRED",
  "sessionDenyResult": ["FINISHED"],
  "pendingAfterDeny": 0,
  "denyDoesNotReask": "AUTHORIZATION_REQUIRED",
  "mutationRefusedAfterTakeover": "REINSPECTION_REQUIRED",
  "blockedProbeAbsent": true,
  "mutationAllowedAfterReinspect": "succeeded",
  "sessionStopped": true,
  "addonDisabled": true
}
```

Combined with the client run above, this covers both approval surfaces with real clicks
simulated through the operators the panels draw: refusal has no side effect, approval is
consumed once, rollback restores the scene, denial does not re-prompt, and user takeover
invalidates outstanding work until the scene is inspected again.

The same run is what exposed the socket path budget: with an Add-on-generated session id the
Unix socket name overflowed `sun_path` and Blender failed with `OSError: AF_UNIX path too
long`. Socket names are now derived from a short hash and the path budget is checked, with
`tests/test_transport_paths.py` guarding both.
