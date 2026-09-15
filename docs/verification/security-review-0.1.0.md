# v0.1.0 Security Review

> Review date: 2026-09-15  
> Scope: stdio MCP runtime, Blender Add-on, installers, release builder, public tool catalog  
> Result: suitable for prerelease; not a production-readiness claim

## Summary

| Severity | Count | Disposition |
|:---|---:|:---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 3 | Documented prerelease limits |
| Low | 2 | Follow-up hardening |

## Verified controls

- The public MCP catalog excludes vendor uploader commands, `advanced.execute_python`, and the authorization-minting tool.
- Gated Harness commands cannot be authorized by a generic MCP client in v0.1.0 and return `AUTHORIZATION_REQUIRED`.
- Session descriptors reject symlinks and group/world-readable mode bits.
- Descriptor tokens are consumed only by the local bridge and omitted from status and tool results.
- macOS uses a private Unix Domain Socket; Windows uses Named Pipe authentication inherited from the Harness.
- Command arguments retain closed schemas and unknown-field rejection.
- Mutations retain transaction and scene-revision checks.
- Installers use user directories, do not require administrator access, and do not open firewall ports.
- Runtime dependencies are empty in `pyproject.toml`.

## Medium risks

1. Windows Add-on foreground interaction and installer execution have CI/runtime work pending. The package is labeled prerelease and Windows remains `DOCUMENTED_NOT_RUN`.
2. A trusted local approval UI for gated MCP operations is not implemented. The safe v0.1.0 behavior is denial; destructive workflows are unavailable rather than silently weakened.
3. The Harness protocol remains `codex-blender/v1` during migration. Differential compatibility tests with the original repository remain necessary before removing the old runtime.

## Low risks

1. Internal Blender data-block names still carry some historical `Codex` prefixes. They are not public MCP identities but should migrate with explicit file-compatibility tests.
2. Network transports shown by MiniMax Design are unsupported. Only local stdio is released; HTTP, Streamable HTTP, and SSE need a separate threat model.

## Evidence

```text
python -m unittest discover -s tests
python -m compileall -q src addon scripts
python scripts/package_release.py --output <isolated-directory>
Blender 5.2.1 isolated Add-on install and enable
pip install partme-blender-mcp-runtime-0.1.0.zip in an isolated target
reproducible package comparison and SHA256SUMS verification
```

No live credentials, private keys, API keys, or user projects are included in the release inputs.
