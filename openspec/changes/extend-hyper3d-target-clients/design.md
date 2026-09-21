# Design

`目标 MCP 客户端` 是 OAuth 会话和 Token 的所有者，不是 Hyper3D 账号类型。

- `CODEX`、`CLAUDE`：插件调用已验证的客户端 CLI；客户端保存 OAuth Token。
- `ZCODE`：插件复制 MCP URL；用户在 ZCode 设置的 MCP 服务行点击授权。
- `KIMI`：插件复制 MCP URL；用户在 Kimi MCP 管理界面授权。当前不依赖实验性本地服务 API。
- `OTHER`：插件只复制标准 URL，不猜测客户端配置格式。

手动客户端一律保持 `NOT_AUTHORIZED`，直到未来存在不读取 Token 的稳定状态查询契约；不能仅凭复制地址宣称已授权。

素材认证边界：Poly Haven 公共 API 无凭据；Sketchfab 官方兼容 API Token 与 OAuth 2.0，但 OAuth 要求 PartMe 注册应用和回调地址；Poly Pizza 当前适配器只使用 API Key。
