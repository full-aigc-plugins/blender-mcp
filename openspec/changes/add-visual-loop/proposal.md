## Why

当前运行时只有里程碑预览，没有可复用的单帧截图契约、目标图锁定和结构化视觉评审状态；远程 MCP 客户端也只能得到服务器本地路径，无法可靠取得图片内容。这使“修改—截图—比较—提交/回滚”仍依赖客户端临时脚本，不能形成跨客户端、可审计、可恢复的产品能力。

## What Changes

- 新增 `scene.screenshot`：在授权输出目录生成不可覆盖的 PNG/JPEG 截图，恢复 Blender 相机、帧和渲染状态，并返回带 SHA-256、尺寸、场景版本和来源信息的回执。
- MCP 结果对截图和预览附加标准图片内容块，使 stdio、Streamable HTTP 和 SSE 客户端无需访问 Blender 主机文件系统也能比较图片。
- 新增 `visual_loop.create/status/record_capture/record_verdict/cancel`，锁定目标图并持久化轮次、结构化评分、最佳轮次与停滞状态。
- 视觉 Judge 只给出 `commit`、`rollback` 或 `revise` 建议；场景事务仍由既有 transaction 命令执行，确保 Judge 发生在提交之前。
- 目标图支持授权本地路径或有界 Base64 上传，锁定后以 SHA-256 标识，不允许原地替换。
- 插件 Skill、Fal ProviderAdapter、发布、真实付费任务与跨平台主机验收作为后续交付门禁，不在未发布运行时上伪装完成。

## Capabilities

### New Capabilities

- `visual-artifacts`: 定义可靠截图、目标图锁定、图片回执和跨机器 MCP 图片返回。
- `visual-loop`: 定义视觉轮次、结构化评审、最佳分数、停滞检测及事务建议。

### Modified Capabilities

无。

## Impact

- Harness 命令注册、路径策略、会话风险分类和运行时目录。
- MCP tool result 内容块与远程传输负载。
- 新增持久化视觉循环状态和对应单元/适配器测试。
- 后续需要发布新的 `blender-mcp` Add-on，再更新 `blender-design-plugin/runtime.lock.json` 并加入 `blender-visual-loop` Skill。
