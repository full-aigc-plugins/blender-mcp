## Context

See `proposal.md` for motivation and `specs/hunyuan3d-provider/spec.md` for the observable contract. The current Add-on stores official credentials in Add-on preferences, chooses between two profiles through `hunyuan3d_intl_pro`, and routes every official task through the professional submit/query pair. Submission, polling, download staging, cancellation and transactional import already exist and must remain the only execution path.

## Goals / Non-Goals

**Goals:**

- Replace the boolean account switch with explicit region, service and default task-type settings while retaining backward compatibility.
- Centralize action pairs and capability metadata in a pure-Python registry usable by UI, execution and tests.
- Preserve the current risk, path, cancellation and transaction boundaries.
- Replace the handwritten TC3 transport with the official Tencent Cloud AI3D Python SDK while keeping a narrow adapter boundary.

**Non-Goals:**

- Implement TokenHub authentication in this change.
- Enable texture, topology, component, UV, motion, rigging, profile or conversion requests before their schemas and result contracts are implemented.
- Perform a paid live generation without a user-supplied budget and configured credentials.

## Decisions

### Use a dedicated Hunyuan capability registry

A new pure-Python module owns immutable account/service profiles and capability definitions. UI enums, request routing and poll-action retention read this registry. This avoids extending the inherited community module and prevents task-type conditionals from spreading through the panel and engine.

Alternative considered: add more branches around the existing community `hunyuan_api_profile`. Rejected because it keeps capability knowledge coupled to vendored code and makes future actions harder to audit.

### Separate four configuration dimensions

The model keeps access mode (`OFFICIAL_API` or `LOCAL_API`), credential kind (`TENCENT_CLOUD_API` now), account region, service type and default task type as distinct values. The legacy `hunyuan3d_intl_pro` value remains readable during migration but is no longer rendered as the primary control.

Alternative considered: one combined profile dropdown. Rejected because it conflates authentication, endpoint selection and operation selection.

### Retain capability identity with each asynchronous task

Submission captures the capability identifier and resolved profile before entering the background runner. Polling and result resolution use the captured capability rather than mutable current preferences. This prevents changing the UI default from causing an in-flight professional task to be queried with the rapid action.

### Keep TokenHub as a separate adapter boundary

The registry can declare authentication adapter IDs, but this change only enables `tencent-cloud-api`. No UI option is created for TokenHub until a real adapter, secure credential lifecycle and official request contract exist.

### Reuse the existing safety chain

New submit actions remain behind `paid_generation`; they use the existing provider task registry, authorized path policies, transfer staging and transaction commands. No capability can bypass these layers through a provider-specific direct import.

### Bundle a pinned official SDK for Blender

The Python project declares `tencentcloud-sdk-python-ai3d` and `tencentcloud-sdk-python-common` at the audited version. The Add-on archive bundles only their `tencentcloud` package trees under a private vendor root and loads them through one adapter. This keeps Blender installs functional without mutating Blender's Python environment at runtime, while normal pip installations continue to use declared dependencies.

Alternative considered: run `pip install` from Blender or rely on a workstation-global package. Rejected because it changes the user's environment at runtime, is not reproducible, and would make the installed Add-on behave differently from the release artifact.

Alternative considered: retain handwritten TC3 signing as the primary transport. Rejected because the official documentation recommends the SDK, and hand-maintained request signing and model serialization would duplicate security-sensitive protocol logic.

## Risks / Trade-offs

- [Existing international users only have a boolean preference] → map the legacy flag to the international compatible profile when new enum values are absent and retain the hidden property for rollback.
- [Tencent may migrate additional models to TokenHub] → keep endpoints and actions data-driven and do not claim TokenHub support.
- [Rapid and professional responses may diverge] → keep result parsing capability-aware and add fixtures for both action pairs before enabling them.
- [Remote cancellation is not exposed for every API] → cancellation stops local work and reports `remoteMayContinue=true` when no official cancel action exists.

## Migration Plan

1. Add registry and tests without changing current defaults.
2. Add explicit preferences and map the legacy international flag.
3. Route professional and rapid submission/polling through registry snapshots.
4. Update the configuration UI and install the Add-on into the active Blender profile.
5. Validate no-network fixtures, real Blender rendering and existing MCP regression suites.
6. Rollback by restoring the previous Add-on package; retained legacy preference fields keep old installations readable.
