# Hunyuan3D TokenHub Authentication Specification

## Purpose

为腾讯混元 3D 提供不泄露凭证的 TokenHub CLI OAuth 辅助入口和独立 Bearer API Key 执行通道。

## ADDED Requirements

### Requirement: Independent authentication choice

The Add-on SHALL offer “腾讯云 API 凭证” and “TokenHub API Key” as independent Hunyuan execution authentication choices and SHALL NOT copy values between them.

#### Scenario: TokenHub selected
- **WHEN** the user selects TokenHub API Key
- **THEN** SecretId and SecretKey fields are hidden and the API Key plus optional THCLI OAuth helper are shown

### Requirement: CLI-owned OAuth

The Add-on SHALL use documented THCLI commands for discovery, status and login and SHALL NOT read, modify or expose files under `~/.thcli`.

#### Scenario: CLI missing
- **WHEN** `thcli` cannot be resolved
- **THEN** the UI reports that THCLI must be installed and does not claim authorization

#### Scenario: Login succeeds
- **WHEN** the background login exits successfully and `auth status` returns exit code 0
- **THEN** the Add-on stores only a non-secret authorized state and refreshes the provider card

### Requirement: Honest execution readiness

THCLI OAuth SHALL NOT be treated as AI3D execution readiness. Readiness SHALL require a separately configured TokenHub API Key.

#### Scenario: OAuth authorized without API Key
- **WHEN** THCLI OAuth is authorized but no TokenHub API Key is configured
- **THEN** the provider remains configuration-required and no paid generation is submitted

### Requirement: Official TokenHub 3D transport

The Add-on SHALL call the official HTTPS submit/query endpoints with Bearer authentication, bounded timeouts and redirects disabled, and SHALL normalize results into the existing task/receipt pipeline.

#### Scenario: Paid generation
- **WHEN** an approved professional or rapid generation is submitted with a configured API Key
- **THEN** the Add-on records the remote task id, polls without exposing the key, and sends completed files through authorized-directory transactional import
