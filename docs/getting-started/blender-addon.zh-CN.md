# PartMe Blender MCP：Blender Add-on 安装与操作手册

> 支持状态：**VERIFIED**（Blender 5.2.1 Add-on 安装与 N 面板验证）  
> 适用：Blender 4.2–5.2、macOS / Windows / Linux  
> 核验日期：2026-09-15

> **预发布提醒**：`v0.5.0` 是正式版本。只从 [GitHub Release](https://github.com/full-aigc-plugins/blender-mcp/releases/latest) 下载，并在安装前核对 SHA-256。

## 1. 前置条件

- 已安装 Blender 4.2 或更高版本（[官方下载](https://www.blender.org/download/)）。
- 已安装 PartMe Blender MCP Runtime（参见 [macOS 安装](macos.zh-CN.md) 或 [Windows 安装](windows.zh-CN.md)）。
- 已从 Release 下载 `partme-blender-mcp-addon-0.5.0.zip` 并校验 SHA-256。

## 2. 从磁盘安装 Add-on

1. 打开 Blender，选择 **Edit → Preferences**。

   ![打开 Blender Preferences](../assets/reference/blender-open-preferences.png)

2. 进入 **Add-ons**，点击右上角菜单，选择 **从磁盘安装…**。

   ![从磁盘安装](../assets/reference/blender-install-from-disk.png)

3. 选择 `partme-blender-mcp-addon-0.5.0.zip`。不要解压。
4. 搜索并启用 **PartMe Blender MCP**。

不要把社区插件 **MCP for Blender** 当作 PartMe Add-on。

## 3. N 面板控件说明

回到 3D View，按 `N` 打开侧栏，选择 **PartMe MCP** 页签。

| 控件 | 类型 | 说明 |
|:---|:---|:---|
| Output（输出目录） | 目录路径 | **必填**。MCP 导出的文件必须位于此目录下。点击 Start 前必须先选择。 |
| Assets（素材目录） | 目录路径 | 可选。图片贴图和导入素材的允许读取目录。 |
| Mode（执行模式） | 枚举 | `interactive`（默认）：审查里程碑；`auto_with_budget`：自动完成授权任务并导出；`review_only`：只读检查，不修改场景或导出。 |
| Design missing assets | 复选框 | 默认关闭。启用后允许 Harness 为缺失素材生成占位代理。 |
| Start MCP Server | 按钮 | 未连接时显示。需要已选输出目录才能启动。 |
| Approve once / 批准一次 | 按钮 | 对待批准列表中的具体 request ID 授权一次；客户端必须用同一 ID 重试。 |
| Deny / 拒绝 | 按钮 | 拒绝该请求并清除待批准项。 |
| Revoke Access | 按钮 | 撤销授权并断开 MCP 连接。 |

## 4. 连接状态

- **未连接**（Not connected）：显示输出目录、素材目录、执行模式、Design missing assets 和 Start MCP Server 按钮。
- **已连接**（Connected）：仅显示连接状态标签和 Revoke Access 按钮。其他控件隐藏。

连接成功后，MCP 客户端可以调用 `blender_connection_status` 和 `blender_scene_inspect`。但客户端本身还需要在其配置中注册 `partme_blender` 服务才能使用工具——仅 Add-on 连接不等于客户端可用。

## 5. 配置客户端

Add-on 启动后，还需要在 MCP 客户端侧配置：

- [Codex](codex.zh-CN.md)
- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [通用 MCP Client](generic-mcp.zh-CN.md)

## 6. 只读验收

客户端加载 `partme_blender` 后，只调用：

```text
blender_connection_status
blender_scene_inspect
```

通过条件：`connected` 为 `true`；Blender 版本与窗口一致；场景对象可读取；回执没有私有 token；N 面板显示 Connected。连接成功不授权删除、覆盖、专家 Python 或最终导出。

## 7. 升级 Add-on

1. 在 N 面板点击 **Revoke Access**。
2. 退出 MCP 客户端。
3. 在 Preferences → Add-ons 中禁用 **PartMe Blender MCP**。
4. 从磁盘安装新版 ZIP（参见第 2 节）。
5. 重新启用并执行只读验收。

详细步骤参见 [升级手册](upgrade.zh-CN.md)。

## 8. 卸载 Add-on

1. 点击 **Revoke Access**。
2. 进入 **Edit → Preferences → Add-ons**，搜索 PartMe。
3. 禁用 **PartMe Blender MCP**。Blender 提示时可选择移除。
4. 删除自行选择的 Runtime 目录。

保留：用户 `.blend` 文件、渲染输出、素材和 checkpoint 目录。详细步骤参见 [卸载手册](uninstall.zh-CN.md)。

## 9. 常见错误

| 症状 | 原因 | 处理 |
|:---|:---|:---|
| 找不到 Add-on | ZIP 未放在顶层为 `partme_blender_mcp/` | 确认 ZIP 来自 Release，重启 Blender 重新安装 |
| Start 按钮灰显或报错 | 未选择输出目录 | 先在 Output 控件选择一个目录 |
| 多窗口时行为异常 | 多个 Blender 会话冲突 | 停止写操作，明确选择目标窗口 |
| 客户端调用报 `BLENDER_NOT_CONNECTED` | N 面板未点击 Start | 在 3D View 侧栏点击 Start MCP Server |
