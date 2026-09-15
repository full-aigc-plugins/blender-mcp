# PartMe Blender MCP：Claude Desktop 操作手册

> 客户端状态：**DOCUMENTED_NOT_RUN**  
> 推荐分发：Claude Desktop Extension（`.dxt`）  
> 核验日期：2026-09-15

## 1. 前置安装

先完成 [macOS](macos.zh-CN.md) 或 [Windows](windows.zh-CN.md) 安装，并在 Blender 中启用 **PartMe Blender MCP**、点击 **Start MCP Server**。

Claude Desktop 的远程 Connector 与本地 stdio 扩展不是一回事。PartMe Blender MCP V1 是本地 stdio，不应填写到远程 Connector URL。

## 2. 推荐方式：安装 DXT

Anthropic 当前推荐用 Desktop Extension 分发本地 MCP：

1. 打开 Claude Desktop。
2. 进入 **Settings → Extensions**。
3. 打开 **Advanced settings**。
4. 在 Extension Developer 区域点击 **Install Extension…**。
5. 选择未来 Release 提供的 `partme-blender-mcp-<version>.dxt`。
6. 检查扩展权限并确认安装。
7. 重启 Claude Desktop 或刷新 Extensions。

> 当前仓库尚未生成 `.dxt`，因此本步骤是发布合同，不能声称已经可用。

## 3. 开发者回退方式

仅当当前 Claude Desktop 版本明确启用了本地开发 MCP 时，才配置本地 stdio。不要把下面内容粘贴到远程 Connector：

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

不同 Claude Desktop 版本对本地开发配置入口可能不同，应以 **Settings → Extensions** 中实际显示的开发者设置为准，不猜测旧版 JSON 文件路径。

## 4. 验证

在新对话中要求：

```text
只调用 blender_connection_status 检查 PartMe Blender MCP。
连接成功后调用 blender_scene_inspect，不修改场景。
```

预期服务名为 `partme_blender`，工具包含 `blender_connection_status` 和 `blender_scene_inspect`。Claude 默认应在调用工具前展示审批。

## 5. 排错

- 扩展已安装但工具缺失：重启 Claude Desktop，检查 Extensions 状态和日志。
- 显示 Runtime 模块不存在：确认扩展/Runtime 使用的 Python。
- 显示 Blender 未连接：回到 Blender 点击 Start MCP Server。
- 企业设备无法安装：组织策略可能禁止本地开发 MCP 或未签名 DXT，请联系管理员，不绕过策略。
- 看到远程 OAuth：说明走错了远程 Connector 路径。

## 6. 停用与卸载

1. Blender 点击 **Revoke Access**。
2. Claude Desktop → Settings → Extensions。
3. 停用或卸载 PartMe Blender MCP。
4. 私下分发的 DXT 升级通常需要重新安装新版。
5. 不删除 Blender 工程和输出目录。

## 7. 延伸

- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [通用 MCP](generic-mcp.zh-CN.md)
