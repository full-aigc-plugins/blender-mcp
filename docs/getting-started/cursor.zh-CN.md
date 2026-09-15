# PartMe Blender MCP：Cursor 操作手册

> 客户端状态：**DOCUMENTED_NOT_RUN**  
> 传输：本地 `stdio`  
> 核验日期：2026-09-15

## 1. 前置安装

完成 [macOS](macos.zh-CN.md) 或 [Windows](windows.zh-CN.md) 安装，并在 Blender 点击 **Start MCP Server**。

## 2. 选择配置范围

Cursor 支持：

- 全局：`~/.cursor/mcp.json`，对所有项目可用。
- 项目：`.cursor/mcp.json`，仅对当前项目可用，可随项目共享。

不要在同一台机器的两个位置重复使用同名 `partme_blender`。

## 3. 写入 mcp.json

```json
{
  "mcpServers": {
    "partme_blender": {
      "command": "python",
      "args": ["-m", "partme_blender_mcp"]
    }
  }
}
```

macOS 可将 `command` 替换为 `command -v python3` 的结果。Windows 可填写 Python 可执行文件绝对路径。路径和参数必须分开。

## 4. 启用与审批

1. 保存 `mcp.json`。
2. 重新加载 Cursor 窗口或打开 MCP 设置。
3. 确认 `partme_blender` 为 enabled。
4. 保持默认工具审批；不要为首次验证开启自动运行。
5. 展开工具调用，检查参数后再允许写操作。

## 5. 验证

Cursor Agent CLI 可检查：

```bash
cursor-agent mcp list
cursor-agent mcp list-tools partme_blender
```

然后在 Agent 中要求：

```text
调用 blender_connection_status。
连接成功后调用 blender_scene_inspect，只读列出当前场景。
```

这两条是只读冒烟。工具名称中不应出现连续双下划线。

## 6. 排错

- MCP 未出现：确认文件位置和 JSON 格式。
- `python` 找不到：填写绝对路径。
- 工具列表不完整：客户端必须读取 `nextCursor`。
- Blender 未连接：在 N 面板点击 Start MCP Server。
- Agent 自动修改：关闭 Auto-run，并在 Blender Revoke Access。
- 项目配置提示不可信：核对仓库来源，不要盲目批准项目内 MCP。

## 7. 移除

从对应 `mcp.json` 删除 `partme_blender` 条目，重新加载 Cursor，并在 Blender Revoke Access。不要删除其他 MCP 配置。

## 8. 其他指南

- [Codex](codex.zh-CN.md)
- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [通用 MCP](generic-mcp.zh-CN.md)
