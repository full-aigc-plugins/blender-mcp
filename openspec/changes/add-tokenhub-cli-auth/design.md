# Design

## Decisions

### THCLI owns credentials

The adapter invokes only documented commands (`--version`, `auth status`, `auth login`). It never opens `~/.thcli/*.credential`, never returns command output containing credentials, and never copies tokens into Blender properties, logs or receipts.

### Exit-code status contract

`thcli auth status` exit code 0 means authorized. Non-zero means login is required or the CLI failed. Optional JSON output is reduced to an allowlisted, non-secret summary.

### Browser login stays alive

`thcli auth login` runs as a background child with a private mode-0600 log. Blender polls the child and then rechecks `auth status`. Escape is the only UI path that terminates a live login process.

### OAuth and model API Key are separate

THCLI OAuth remains CLI-owned and is never exported. TokenHub 3D execution uses the separately created Bearer API Key documented by the model API. Blender stores that key only in its local user preferences and never places it in task payloads, receipts, copied URLs or logs.

### One transport, capability registry

All documented TokenHub 3D models share bounded HTTPS submit/query endpoints. A transport adapter owns authentication, timeouts, response validation and normalization; a registry maps independent capabilities such as generation, texture, UV, retopology, rigging and motion to model identifiers.

## Rejected alternatives

- Reading `~/.thcli/*.credential`: violates the official ownership boundary and couples the Add-on to a private file schema.
- Parsing or exporting access/refresh tokens: risks credential disclosure and bypasses THCLI refresh handling.
- Treating THCLI OAuth state as a Bearer model credential: the official 3D API requires a separate API Key.
- Installing THCLI from Blender: package installation is an explicit user/admin action and must not happen inside the Add-on.
