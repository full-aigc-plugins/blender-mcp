# PartMe Blender MCP：Claude Code 操作手册

> 客户端状态：**DOCUMENTED_NOT_RUN**  
> 传输：本地 `stdio`  
> 核验日期：2026-09-15

## 1. 前置安装

先完成 [macOS](macos.zh-CN.md) 或 [Windows](windows.zh-CN.md)，并在 Blender 点击 **Start MCP Server**。

## 2. 注册用户级 MCP

官方 Claude Code 语法要求选项位于服务名之前，并用 `--` 分隔实际启动命令：

```bash
claude mcp add --transport stdio --scope user partme_blender -- python -m partme_blender_mcp
claude mcp list
```

作用域：

- `--scope user`：当前用户所有项目。
- `--scope local`：当前项目、本机私有配置。
- `--scope project`：写入项目 `.mcp.json`，团队成员加载时会收到信任提示。

不要把 Python 命令放在 `--` 前面。

## 3. 检查连接

启动 Claude Code 后输入：

```text
/mcp
```

确认 `partme_blender` 已连接。然后要求：

```text
调用 blender_connection_status，再调用 blender_scene_inspect；仅检查，不修改 Blender。
```

这两条工具是只读冒烟测试。工具存在但 Blender 未连接时，检查 N 面板的 Start MCP Server。

## 4. 权限

项目级 `.mcp.json` 首次使用会触发信任选择。只信任来自本仓库固定 Release 的命令。Claude Code 的工具批准不能替代 Blender Harness 对删除、覆盖、专家 Python 和最终导出的授权。

## 5. 项目级配置示例

```json
{
  "mcpServers": {
    "partme_blender": {
      "command": "python",
      "args": ["-m", "partme_blender_mcp"],
      "env": {}
    }
  }
}
```

配置不包含云端 API Key。Runtime 与 Blender 在本机通信。

## 6. 排错与移除

```bash
claude mcp list
claude mcp remove --scope user partme_blender
```

如果当前 CLI 的 remove 参数发生变化，先运行 `claude mcp remove --help`，不要删除整个 Claude 配置文件。

常见问题：

- `spawn python ENOENT`：填写 Python 绝对路径。
- 超时：检查 Blender 是否暂停；`AUTHORIZATION_REQUIRED` 需要先在 Blender 本地批准，再用同一 request ID 重试。
- 工具不完整：客户端必须跟随 `tools/list` 的 `nextCursor`。
- 多个会话：通过明确描述符绑定目标窗口。

## 7. 其他指南

- [Claude Desktop](claude-desktop.zh-CN.md)
- [Codex](codex.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [通用 MCP](generic-mcp.zh-CN.md)
