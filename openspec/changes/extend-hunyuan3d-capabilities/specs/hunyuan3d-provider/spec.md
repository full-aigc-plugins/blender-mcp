## Purpose

为腾讯混元 3D 提供可扩展、可审计的供应商契约，使不同账户区域、服务类型和生成任务共享一致的付费审批、取消、受控下载及事务导入安全边界。

## ADDED Requirements

### Requirement: Stable provider identity and explicit credential type
The Add-on SHALL display the provider as “腾讯混元 3D” and SHALL identify official-cloud configuration as “腾讯云 API 凭证”.

#### Scenario: User opens the model tab
- **WHEN** the model provider list is rendered
- **THEN** the card displays “腾讯混元 3D” without splitting task types into separate provider cards

#### Scenario: User opens official-cloud configuration
- **WHEN** official Tencent Cloud API mode is selected
- **THEN** the configuration view displays “腾讯云 API 凭证”, SecretId and SecretKey controls

### Requirement: Region and service configuration
The Add-on SHALL persist account region and service type as separate values and SHALL reject unsupported combinations before network access.

#### Scenario: Mainland AI3D account
- **WHEN** the user selects mainland account region and AI3D service
- **THEN** the system uses the mainland AI3D service profile and does not add international compatibility fields

#### Scenario: International legacy service
- **WHEN** the user selects international account region and compatible Hunyuan service
- **THEN** the system uses the international service profile and required compatibility fields

#### Scenario: Invalid combination
- **WHEN** a task requests a region and service combination not declared by the registry
- **THEN** the system rejects it before signing or sending a request

### Requirement: Professional and rapid task types
The provider SHALL support professional and rapid generation as independently registered task types with distinct submit and query actions.

#### Scenario: Professional generation
- **WHEN** a paid generation request selects the professional task type
- **THEN** the professional submit action is used and its matching query action is retained with the task

#### Scenario: Rapid generation
- **WHEN** a paid generation request selects the rapid task type
- **THEN** the rapid submit action is used and its matching query action is retained with the task

### Requirement: Official SDK transport
The provider SHALL use the pinned official Tencent Cloud AI3D Python SDK for credential signing, request model serialization, HTTPS dispatch and response deserialization. It SHALL NOT install packages at Add-on runtime or fall back silently to handwritten signing.

#### Scenario: Normal Python package installation
- **WHEN** the runtime is installed with pip
- **THEN** the AI3D SDK and common SDK are resolved from declared project dependencies

#### Scenario: Blender Add-on installation
- **WHEN** the release Add-on ZIP is installed into Blender
- **THEN** the same pinned SDK implementation is available from the private bundled vendor root without a separate pip command

#### Scenario: SDK request fails
- **WHEN** the official SDK raises a credential, transport or API exception
- **THEN** the provider returns a sanitized Harness error and does not automatically retry a paid submission

### Requirement: Extensible capability registry
The system SHALL describe each Hunyuan capability through a registry entry containing identity, label, submit action, query action, supported services, input modes, result type and risk.

#### Scenario: Future capability registration
- **WHEN** a texture, topology, component, UV, motion, rigging, profile or conversion capability is added
- **THEN** it can be registered without adding another provider card or modifying the credential model

#### Scenario: Unsupported capability
- **WHEN** a caller requests an unregistered capability
- **THEN** the system returns a closed-schema invalid-argument error before network access

### Requirement: Paid-operation safety chain
Every cloud submission that may consume credits SHALL pass through the existing paid-generation policy, support local cancellation semantics, read local inputs only from authorized asset roots, stage downloaded results under the authorized output root, and import through a Blender transaction with a receipt.

#### Scenario: Submission requires approval
- **WHEN** the configured budget does not authorize a paid submission
- **THEN** no Tencent Cloud request is sent until Blender grants the exact pending authorization

#### Scenario: Task cancellation
- **WHEN** the user terminates a running task
- **THEN** local polling and result consumption stop and the task reports whether the remote task may continue

#### Scenario: Generated result import
- **WHEN** a completed result is imported into Blender
- **THEN** the file is first staged under the authorized output root and the scene mutation is committed or rolled back as one transaction with a receipt

### Requirement: TokenHub isolation
TokenHub SHALL be represented only by a future independent authentication adapter and SHALL NOT reuse, overwrite or infer existing SecretId and SecretKey values.

#### Scenario: Traditional API configuration exists
- **WHEN** SecretId and SecretKey have been configured
- **THEN** no TokenHub credential or authentication state is inferred

#### Scenario: TokenHub is unavailable
- **WHEN** the current release has no TokenHub adapter
- **THEN** TokenHub is not offered as a usable authentication choice
