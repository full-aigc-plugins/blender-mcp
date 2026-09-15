# PartMe Blender MCP：通用 MCP Client 手册

> 客户端状态：**DOCUMENTED_NOT_RUN**  
> 协议基线：MCP 2025-06-18、`stdio`  
> 核验日期：2026-09-15

## 1. 前置条件

完成 [macOS](macos.zh-CN.md) 或 [Windows](windows.zh-CN.md) 安装，在 Blender 启用 **PartMe Blender MCP** 并点击 **Start MCP Server**。

客户端必须支持本地 stdio MCP、JSON-RPC 2.0、Tools 和分页。

## 2. 通用配置

```json
{
  "mcpServers": {
    "partme_blender": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "partme_blender_mcp"],
      "env": {}
    }
  }
}
```

若客户端不接受 `type`，按其 schema 删除该字段；不要猜测额外字段。命令必须来自固定 Runtime，不能指向临时缓存。

## 3. stdio 进程合同

- 客户端启动 `python -m partme_blender_mcp`。
- stdin/stdout 只传递一行一个 JSON-RPC 消息。
- Runtime 日志只能写 `stderr`，不得污染 stdout。
- 工作目录不是安全边界；Runtime 应能从安装位置启动。
- 进程继承最小环境，不需要 Blender 云端账号或 API Key。

## 4. MCP 生命周期

客户端依次执行：

1. `initialize`，协商支持的协议版本。
2. `notifications/initialized`，不等待响应。
3. `tools/list`，读取第一页。
4. 如果返回 `nextCursor`，继续调用 `tools/list`，直到没有 cursor。
5. `tools/call` 调用所选工具。
6. 客户端退出时关闭 stdin，Runtime 安全结束。

工具结果包含文本 `content`，并可包含 `structuredContent`。客户端不应丢弃结构化回执。

## 5. 工具安全

`annotations` 只是提示，不能替代授权。客户端应展示工具名和参数；Harness 仍负责事务、scene revision、路径、删除/覆盖及专家 Python 授权。

工具名示例：

```text
blender_connection_status
blender_scene_inspect
blender_object_create_mesh
blender_animation_pose_keyframe
```

## 6. 只读握手

先调用：

```text
blender_connection_status
blender_scene_inspect
```

服务 ID 是 `partme_blender`。通过条件是活动会话唯一、场景可读、无 token 泄漏、无双下划线旧名。

## 7. 错误处理

- `BLENDER_NOT_CONNECTED`：指导用户在 Blender 点击 Start MCP Server。
- `AMBIGUOUS_SESSION`：让用户选择窗口，不能自动重试所有描述符。
- `STALE_SCENE_REVISION`：重新检查场景并开启新事务。
- `AUTHORIZATION_REQUIRED`：显示具体动作并等待；用户在 Blender 选择“批准一次”或“拒绝”，批准后用同一 request ID 重试。
- MCP 解析错误：保留 stderr 日志，不把无效输出拼回 JSON-RPC。

## 8. 网络传输

V1 不提供 HTTP、Streamable HTTP 或 SSE 公网部署。客户端即使支持这些协议，也不能把本地 stdio Runtime 当成网络服务暴露。

## 9. 客户端指南

- [Codex](codex.zh-CN.md)
- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
