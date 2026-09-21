## 1. Contract

- [x] 1.1 增加五类目标 MCP 客户端与自动/手动边界测试。
- [x] 1.2 增加素材认证文案测试。

## 2. Implementation

- [x] 2.1 扩展目标客户端枚举并重命名字段。
- [x] 2.2 保留 Codex/Claude Code 自动授权，增加 ZCode/Kimi/其他客户端复制配置流程。
- [x] 2.3 防止手动客户端被 CLI 状态探测误判为已授权。
- [x] 2.4 在素材配置中说明 Sketchfab OAuth、API Token 和 Poly Pizza API Key 边界。

## 3. Verification

- [x] 3.1 运行目标单元测试。
- [x] 3.2 运行完整回归、严格 OpenSpec 校验与发布包检查。
- [x] 3.3 安装到真实 Blender 并验证五项枚举、手动授权边界和素材文案注册。
