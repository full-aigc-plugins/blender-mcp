# Provider Integration Implementation Plan

**Spec:** `docs/superpowers/specs/2026-09-19-provider-integration-design.md`

- [x] 统一当前版本事实源并增加防漂移测试。
- [x] 新增供应商注册表、状态协议和原生供应商定义。
- [x] 将 Poly Pizza/fetch_url 原生命令迁移到 `blender-mcp`。
- [x] 增加权限、资产库、AI 模型通用 Blender 子面板。
- [x] 按 `docs/design/partme-blender-mcp-sidebar-ui-v1.md` 实现默认展开、自动生成进度、终止生成和完整快捷操作。
- [x] 在插件侧增加社区供应商贡献清单并由自动安装写入 Add-on。
- [x] 移除社区 Poly Pizza 和直接导入公共主路径，增加风险分类。
- [x] 修复 `PluginMcpAdapter` 跨页唯一性并增加真实适配器测试。
- [x] 为 `scripts/harness/` 建立声明式差分门禁。
- [x] 更新活动 README、仓库 URL 和验证状态。
- [ ] 构建 `blender-mcp 0.5.1` 最终资产，更新插件 runtime lock。
- [ ] 运行单元、分发、真实 Blender 与客户端矩阵验收。
- [ ] 发布 runtime、插件和市场清单；分别记录远端与安装证据。

## V4.2 真实联动增量

- [x] 为注册表增加独立`enabled/mutable/configurable/toggleLocked`状态、真实可用数和路由门禁测试。
- [x] 将社区供应商启用偏好同步到真实`blendermcp_use_*`属性，并为插件适配器增加禁用门禁。
- [x] 将 Blender 侧栏重构为单工作台四 Tab，保留制作快捷操作和本地审批。
- [x] 增加真实供应商启停 Operator、定向配置入口、busy 锁定和任务终止联动。
- [x] 使用 Blender 用户配置持久化供应商偏好，不把密钥或偏好写入`.blend`。
- [x] 完成定向单元测试、静态 Add-on 合约测试、可复现打包和真实 Blender 供应商启停验收。
- [x] 在可见 Blender UI 中完成`240 px`窄宽度、四 Tab、错误、密钥缺失、生成中和审批截图验收。
- [x] 用官方 MCP Python SDK 替换自写 stdio，并实现真实 Streamable HTTP/SSE 监听器及远程安全设置。
