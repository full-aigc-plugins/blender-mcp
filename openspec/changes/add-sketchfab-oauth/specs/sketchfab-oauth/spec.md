# sketchfab-oauth Specification

## ADDED Requirements

### Requirement: Sketchfab 双认证模式

系统 SHALL 提供 API Token 与 OAuth 2.0，并为所有 Sketchfab API 能力使用所选模式对应的认证头。

#### Scenario: API Token 调用

- **WHEN** 用户选择 API Token 并配置 Token
- **THEN** Sketchfab 请求使用 `Authorization: Token` 认证

#### Scenario: OAuth 调用

- **WHEN** 用户完成 OAuth 浏览器授权
- **THEN** Sketchfab 请求使用 `Authorization: Bearer` 认证

### Requirement: OAuth 回调安全

系统 SHALL 只监听已配置的本机回调地址，并校验随机 state 后交换授权码。

#### Scenario: 回调 state 不匹配

- **WHEN** 回调 state 与发起授权时不一致
- **THEN** 系统拒绝交换授权码且不保存任何 Token

#### Scenario: 授权成功

- **WHEN** 授权码交换返回有效 Bearer Token
- **THEN** 系统保存 Token 状态、刷新供应商并显示居中的成功页
