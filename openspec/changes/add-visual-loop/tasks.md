## 1. 可靠视觉证据

- [x] 1.1 为截图状态恢复、失败恢复、路径限制、不可覆盖和回执完整性增加失败测试。
- [x] 1.2 实现 `scene.screenshot` 及图片签名、尺寸、哈希验证。
- [x] 1.3 为 MCP 截图与预览图片内容块增加失败测试并实现跨机器返回。

## 2. 视觉循环状态

- [x] 2.1 为本地/上传目标锁定、状态恢复、取消和原子持久化增加失败测试。
- [x] 2.2 实现 `visual_loop.create/status/record_capture/cancel`。
- [x] 2.3 为 VisualVerdict、最佳轮次、停滞、耗尽和事务建议增加失败测试。
- [x] 2.4 实现 `visual_loop.record_verdict` 和确定性状态转移。

## 3. 运行时集成与验证

- [x] 3.1 注册命令、模式、风险、能力元数据和会话只读分类，并验证 MCP 工具分页唯一性。
- [x] 3.2 运行目标测试、完整单元测试、Ruff、OpenSpec 严格校验和发布包检查。
- [x] 3.3 在真实 Blender 中验证成功/失败截图状态恢复和至少一个 Streamable HTTP 图片响应。

## 4. 插件与真实验收

- [x] 4.1 发布新的不可变 `blender-mcp` RC，验证资产和远端 CI 后更新插件 `runtime.lock.json`。
- [x] 4.2 新增 `blender-visual-loop` Skill，分别描述支持子智能体和单智能体客户端的编排策略。
- [ ] 4.3 若确需 Fal，以独立 ProviderAdapter 接入费用、提交不确定性、轮询和远端终止语义。
- [ ] 4.4 验证 stdio/HTTP/SSE、Codex/Claude Code/ZCode/Kimi、macOS/Windows，并用真实目标图复现一次 0 到至少 8 分。
