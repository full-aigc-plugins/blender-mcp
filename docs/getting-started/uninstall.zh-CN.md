# PartMe Blender MCP：卸载手册

> 支持状态：**VERIFIED**（Blender 5.2.1 Add-on 卸载与 Runtime 清理验证）  
> 适用：Blender 4.2–5.2、macOS / Windows / Linux  
> 核验日期：2026-09-15

> **预发布提醒**：`v0.5.2` 是正式版本。卸载前确认已完成当前工作并备份重要文件。

## 1. 卸载前确认

卸载 PartMe Blender MCP 不会删除你的 Blender 工程或渲染输出，但请确认：

- 所有需要保留的 `.blend` 文件已保存。
- 渲染输出和导出文件已备份到安全位置。
- 没有正在进行的 MCP 任务（后台任务会在连接断开时中止）。

## 2. 完整卸载顺序

按以下顺序操作，不要跳步：

### 第 1 步：撤销 Blender 端授权

在 Blender 的 **PartMe MCP** N 面板中点击 **Revoke Access**。这会断开 MCP 连接并使所有活跃事务失效。

### 第 2 步：从 Blender 卸载 Add-on

1. 打开 **Edit → Preferences → Add-ons**。
2. 搜索 PartMe。
3. 禁用 **PartMe Blender MCP**。
4. Blender 提示时可选择移除 Add-on 文件。

### 第 3 步：从 MCP 客户端移除配置

在每个使用过 `partme_blender` 的客户端中移除 MCP 配置：

```bash
# Codex
codex mcp remove partme_blender

# Claude Code
claude mcp remove --scope user partme_blender
```

Claude Desktop、Cursor、MiniMax Design 等客户端：编辑对应的 MCP 配置文件，删除 `partme_blender` 条目。

移除 MCP 配置不会删除 Blender 工程或导出文件。

### 第 4 步：删除 Runtime 目录

根据平台删除安装目录：

```bash
# macOS
rm -rf "$HOME/Library/Application Support/PartMe/BlenderMCP"
```

```powershell
# Windows
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\PartMe\BlenderMCP"
```

手动 pip 安装的用户：

```bash
python -m pip uninstall partme-blender-mcp
```

## 3. 必须保留的文件

以下文件不属于 PartMe Blender MCP，卸载时**不要删除**：

| 文件类型 | 位置 |
|:---|:---|
| 用户 `.blend` 工程 | 你保存工程的任意目录 |
| 渲染输出 | N 面板中设置的 Output 目录 |
| 素材文件 | N 面板中设置的 Assets 目录 |
| Checkpoint 目录 | Runtime 工作目录下的快照 |

## 4. 确认无残留

卸载完成后，运行以下检查：

```bash
python -m partme_blender_mcp doctor --json
```

如果命令不存在，说明 Runtime 已成功移除。如果仍然可用，确认是否还有其他 Python 环境安装了该包。

检查描述符和套接字目录是否已清理：

```bash
# macOS：确认临时目录无残留
ls /tmp/partme-blender-* 2>/dev/null || echo "无残留"
```

```powershell
# Windows：确认 Named Pipe 已消失
# 正常情况下 Revoke Access 后管道自动关闭
```

## 5. 注意事项

- 卸载 PartMe Blender MCP 不等于卸载 Blender 本身。
- 卸载 PartMe Blender MCP 不等于卸载 MCP 客户端（Codex、Claude Desktop 等）。
- 如果将来重新安装，需要从 Release 下载并重新走完整安装流程。
- 卸载后 `blender_connection_status` 等工具将不再可用。

## 6. 相关文档

- [Blender Add-on 安装与操作](blender-addon.zh-CN.md)
- [升级手册](upgrade.zh-CN.md)
- [macOS 安装](macos.zh-CN.md)
- [Windows 安装](windows.zh-CN.md)
