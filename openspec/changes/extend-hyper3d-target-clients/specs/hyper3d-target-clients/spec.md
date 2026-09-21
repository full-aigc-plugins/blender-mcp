# hyper3d-target-clients Specification

## ADDED Requirements

### Requirement: 目标客户端完整且不虚假自动化

界面 SHALL 提供 Codex、Claude Code、ZCode、Kimi 与其他 MCP 客户端。系统 SHALL 只对已有稳定 CLI 契约的客户端执行自动配置。

#### Scenario: 自动客户端授权

- **WHEN** 用户选择 Codex 或 Claude Code 并点击授权
- **THEN** 系统通过对应 CLI 配置 Hyper3D MCP 并由客户端保管 OAuth Token

#### Scenario: 手动客户端授权

- **WHEN** 用户选择 ZCode、Kimi 或其他 MCP 客户端
- **THEN** 系统复制 Hyper3D Streamable HTTP 地址并提示在目标客户端完成 OAuth
- **AND** 系统不得把复制动作标记为已授权

### Requirement: 素材认证说明与真实能力一致

素材供应商配置 SHALL 区分无凭据、API Key/API Token 与 OAuth，并不得展示尚未实现的可操作授权入口。

#### Scenario: Sketchfab 配置

- **WHEN** 用户打开 Sketchfab 配置
- **THEN** 系统说明官方支持 OAuth 2.0，但当前插件使用 API Token
- **AND** 系统说明启用 OAuth 需要注册应用与回调地址
