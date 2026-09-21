# Change: 扩展 Hyper3D OAuth 目标 MCP 客户端

## Why

Hyper3D OAuth 的凭据由目标 MCP 客户端保管，而不是由 Blender 保管。现有界面只列出 Codex 与 Claude Code，无法表达 ZCode、Kimi 和其他兼容客户端，同时也容易把“支持该客户端”误解为 Blender 能替它完成授权。

## What Changes

- 目标 MCP 客户端增加 Codex、Claude Code、ZCode、Kimi、其他 MCP 客户端。
- Codex 与 Claude Code保留已验证的 CLI 自动配置与浏览器 OAuth。
- ZCode、Kimi 和其他客户端只复制标准 Streamable HTTP 地址，并明确要求在目标客户端完成 OAuth。
- 不探测、不读取手动客户端的凭据或本地密钥。
- 素材配置页明确 Sketchfab、Poly Haven 与 Poly Pizza 的真实认证边界。

## Impact

- Affected specs: `hyper3d-target-clients`
- Affected code: Hyper3D OAuth adapter, Blender provider preferences/operator/UI, layout and auth tests
