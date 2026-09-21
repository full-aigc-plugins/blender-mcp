## 1. Capability Contract

- [x] 1.1 Add failing tests for professional/rapid registry entries, supported profile combinations and future capability reservations.
- [x] 1.2 Implement the immutable Hunyuan capability and account/service profile registry.

## 2. Configuration and UI

- [x] 2.1 Add failing tests for the “腾讯云 API 凭证” heading, SecretId/SecretKey, account region, service type and task type controls.
- [x] 2.2 Implement explicit preferences and backward-compatible migration from the international Pro boolean.
- [x] 2.3 Update the model card and provider configuration dialog without adding a second provider card or TokenHub choice.

## 3. Execution Routing

- [x] 3.1 Add failing fixtures for professional and rapid submit/query actions and invalid profile/capability rejection before network access.
- [x] 3.2 Route submission, polling and result resolution through a captured capability/profile snapshot.
- [x] 3.3 Preserve paid-generation approval, cancellation and authorized-input behavior for both task types.

## 4. Verification and Delivery

- [x] 4.1 Run provider, authorization, transfer, transaction and MCP regression suites and validate the OpenSpec change.
- [x] 4.2 Install the updated Add-on into the active Blender profile and verify the real configuration UI at normal and narrow widths.
- [x] 4.3 Record remaining live-service validation limits; do not perform paid generation without a user-provided budget.

## 5. Official SDK Transport

- [x] 5.1 Add failing adapter tests for SDK client configuration, request model serialization, response wrapping and sanitized failures.
- [x] 5.2 Implement a narrow `hunyuan_sdk` adapter and route submission plus automatic/manual polling through it.
- [x] 5.3 Pin the AI3D/common SDK dependencies and bundle their audited package trees, provenance and notices into the Add-on archive.
- [x] 5.4 Verify package contents, deterministic release output, complete regression suite and real Blender import/connectivity without credentials or paid calls.
