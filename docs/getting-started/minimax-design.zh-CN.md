# PartMe Blender MCP：MiniMax Design 操作手册

> 客户端状态：**DOCUMENTED_NOT_RUN**  
> 已确认：存在自定义连接器界面和 `stdio` 选项  
> 未确认：真实握手、分页、工具调用与授权  
> 核验日期：2026-09-15

## 1. 前置安装

先完成 [macOS](macos.zh-CN.md) 或 [Windows](windows.zh-CN.md) 安装。在 Blender 中启用 **PartMe Blender MCP**，打开 N 面板的 **PartMe MCP**，点击 **Start MCP Server**。

## 2. 打开自定义连接器

MiniMax Design 当前界面提供“添加自定义连接器”，支持手动填写和 JSON 配置：

![MiniMax Design 添加自定义连接器](../assets/reference/minimax-design-add-custom-connector.png)

界面已观察到：

- 连接器名称；
- 连接方式；
- 启动命令；
- 启动参数；
- 备注；
- 添加后启用；
- 高级选项。

本文不描述未展开的高级选项。

## 3. 手动填写 stdio

填写：

| 字段 | 内容 |
|---|---|
| 连接器名称 | `partme_blender` |
| 连接方式 | `stdio` |
| 启动命令 | `python` |
| 启动参数 | `-m partme_blender_mcp` |
| 备注 | 本地安全控制 Blender |
| 添加后启用 | 开启 |

如果 MiniMax Design 找不到 `python`：

- macOS：运行 `command -v python3`，把结果填入启动命令。
- Windows：运行 `py -3 -c "import sys; print(sys.executable)"`，填入返回的 `python.exe`，参数改为 `-m partme_blender_mcp`。

启动参数字段如果要求逐项输入，应分别填 `-m` 和 `partme_blender_mcp`，不要把引号作为参数内容。

## 4. JSON 配置

切换到 **JSON 配置** 后使用通用结构：

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

实际 JSON schema 尚需在目标 MiniMax Design 版本中提交并回读验证；如果界面拒绝，不要改成其他客户端的私有字段。

## 5. 连接方式说明

截图确认下拉框有 `stdio`、`HTTP`、`Streamable HTTP` 和 `SSE`：

![MiniMax Design 连接方式](../assets/reference/minimax-design-transport-options.png)

**首版仅正式设计本地 stdio**。HTTP、Streamable HTTP 和 SSE 需要独立认证、监听范围、会话隔离和网络安全设计，目前不能填写本地 Runtime 命令后声称支持。

## 6. 添加与验证

1. 确认“添加后启用”开启。
2. 点击 **添加连接器**。
3. 回到创作对话，确认 `partme_blender` 出现在工具列表。
4. 先调用 `blender_connection_status`。
5. 再调用 `blender_scene_inspect`，要求只读。
6. 确认返回当前 Blender 场景且不包含 token。

由于尚未在 MiniMax Design 中执行真实提交和握手，本手册状态保持 **DOCUMENTED_NOT_RUN**。界面截图不是运行验证。

## 7. 排错

- 启动失败：检查 Python 绝对路径和 Runtime 是否安装。
- 工具列表为空：重新打开连接器配置，确认已启用。
- 工具不全：确认客户端跟随 `nextCursor` 分页。
- Blender 未连接：点击 N 面板 Start MCP Server。
- 等待授权：切回 Blender 查看本地确认。
- 不要改用社区 Add-on 的 9876 端口。

## 8. 停用

先在 Blender 点击 **Revoke Access**，再在 MiniMax Design 停用或删除 `partme_blender`。不要删除 Runtime 目录中的用户工程或输出。

## 9. 其他客户端

- [Codex](codex.zh-CN.md)
- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [通用 MCP](generic-mcp.zh-CN.md)
