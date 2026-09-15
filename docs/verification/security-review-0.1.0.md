# v0.1.0 Security Review

> Review date: 2026-09-15 (revision 2)  
> Scope: stdio MCP runtime, Blender Add-on, installers, release builder, public tool catalog  
> Result: suitable for prerelease; not a production-readiness claim

## Revision 2 (2026-09-15, after the local approval surface)

A trusted **local approval surface** now exists, so gated commands are approvable instead of
only deniable. `Session.approve_pending` records a pending gated request when the Harness
refuses it, and the Blender UI (PartMe MCP Add-on panel and the shared session panel) can
approve or deny that exact request. The claim never travels to the client: the client
succeeds by retrying the same `requestId`. Approval is bound to one `requestId` + command,
expires (default 120 s, max 300 s), is single use, and is dropped on user takeover or
revoke. The transport-claim path (`session.authorize`) is unchanged for host approval bridges.

Verified locally on Blender 5.2.1 with a headless host and a generic stdio MCP client:
a gated `object.delete` returned `AUTHORIZATION_REQUIRED` with no side effect, local approval
allowed exactly one retry of the same request id, the deletion took effect, and a transaction
rollback restored the object. See
[`generic-mcp-handshake-2026-09-15.md`](generic-mcp-handshake-2026-09-15.md).

## Summary

| Severity | Count | Disposition |
|:---|---:|:---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 2 | Documented prerelease limits |
| Low | 2 | Follow-up hardening |

## Verified controls

- The public MCP catalog excludes vendor uploader commands, `advanced.execute_python`, and the authorization-minting tool.
- Gated Harness commands cannot be authorized by a generic MCP client: the client receives `AUTHORIZATION_REQUIRED` and can only proceed after a user approves that exact request id in Blender.
- Local approval is action-bound and single use, expires, and is invalidated by user takeover or revoke.
- Session descriptors reject symlinks and group/world-readable mode bits.
- Descriptor tokens are consumed only by the local bridge and omitted from status and tool results.
- The connecting client's `clientInfo` is recorded at `initialize` and reported by `blender_connection_status`.
- macOS uses a private Unix Domain Socket; Windows uses Named Pipe authentication inherited from the Harness.
- Command arguments retain closed schemas and unknown-field rejection.
- Mutations retain transaction and scene-revision checks.
- Installers use user directories, do not require administrator access, and do not open firewall ports.
- Runtime dependencies are empty in `pyproject.toml`.

## Medium risks

1. Windows Add-on foreground interaction and installer execution have CI/runtime work pending. The package is labeled prerelease and Windows remains `DOCUMENTED_NOT_RUN`.
2. Single-writer client selection is not enforced. One Harness accepts one session, but it does not yet restrict concurrent clients to a single writer or require local confirmation to switch writers, as §5.2 of the design specifies.
3. The Harness protocol remains `codex-blender/v1` during migration. Differential compatibility tests with the original repository remain necessary before removing the old runtime.

## Low risks

1. Internal Blender data-block names still carry some historical `Codex` prefixes (milestone camera names, `_meta.codexBlenderCommand` keys, `codex-blender/v1`). They are not public MCP identities; the user-visible panels and operator ids are PartMe-branded as of revision 2.
2. Network transports shown by MiniMax Design are unsupported. Only local stdio is released; HTTP, Streamable HTTP, and SSE need a separate threat model.

## Evidence

```text
python -m unittest discover -s tests
python -m compileall -q src addon scripts tests
python -m ruff check src addon scripts tests
python scripts/package_release.py --output <isolated-directory>
Blender 5.2.1 isolated Add-on install and enable
pip install partme-blender-mcp-runtime-0.1.0.zip in an isolated target
tests/runtime/generic_mcp_client_handshake.py (live session, gated refusal, local approval, rollback)
reproducible package comparison and SHA256SUMS verification
```

No live credentials, private keys, API keys, or user projects are included in the release inputs.
