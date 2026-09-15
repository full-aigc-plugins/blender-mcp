# PartMe Blender MCP：macOS 安装手册

> 支持状态：**DOCUMENTED_NOT_RUN**  
> 适用：macOS Apple Silicon / Intel、Blender 4.2–5.2  
> 核验日期：2026-09-15

> **预发布提醒**：首个 Runtime Release 尚未发布。以下是正式发行后的操作合同；在 Release 出现对应文件和 SHA-256 前，不要把示例文件名当成已可下载产物。

## 1. 下载两个组件

PartMe Blender MCP 包含：

1. `partme-blender-mcp-runtime-<version>.zip`：由 MCP 客户端启动。
2. `partme-blender-mcp-addon-<version>.zip`：安装到 Blender。

下载入口：

- [PartMe Blender MCP Releases](https://github.com/partme-ai/blender-mcp/releases/latest)
- [Blender 官方下载](https://www.blender.org/download/)
- [Blender 官方目录说明](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html)

Apple Silicon 选择 arm64；Intel Mac 选择 x64。

## 2. 校验下载

把两个压缩包和 `SHA256SUMS.txt` 放在同一目录：

```bash
cd "$HOME/Downloads"
shasum -a 256 partme-blender-mcp-addon-<version>.zip
shasum -a 256 partme-blender-mcp-runtime-<version>.zip
```

输出必须与 `SHA256SUMS.txt` 完全一致。不同则停止安装。

## 3. 检查 Runtime

```bash
python3 --version
command -v python3
```

首版目标为 Python 3.11–3.13，以 Release manifest 为准。不要覆盖系统 Python。将 Runtime 解压到固定的用户目录，例如 `~/Applications/PartMe-Blender-MCP/`。

正式 Runtime 的检查入口为：

```bash
python3 -m partme_blender_mcp --version
python3 -m partme_blender_mcp doctor --json
```

首个 Release 前，这些命令仍是预期接口，不是当前可执行证明。

## 4. 在 Blender 中从磁盘安装

打开 Blender，选择 **Edit → Preferences**：

![打开 Blender Preferences](../assets/reference/blender-open-preferences.png)

进入 **Add-ons**，点击右上角菜单，选择 **从磁盘安装…**：

![从磁盘安装 Blender Add-on](../assets/reference/blender-install-from-disk.png)

然后：

1. 选择 `partme-blender-mcp-addon-<version>.zip`，不要解压。
2. 搜索并启用 **PartMe Blender MCP**。
3. 回到 3D View，按 `N`。
4. 打开 **PartMe MCP** 页签。
5. 选择允许写入的输出目录和允许读取的素材目录。
6. 点击 **Start MCP Server**。

不要把社区插件 **MCP for Blender** 当作 PartMe Add-on。

## 5. 配置客户端

- [Codex](codex.zh-CN.md)
- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [通用 MCP Client](generic-mcp.zh-CN.md)
- [Windows](windows.zh-CN.md)

## 6. 只读验收

客户端加载 `partme_blender` 后，只调用：

```text
blender_connection_status
blender_scene_inspect
```

通过条件：`connected` 为 `true`；Blender 版本与窗口一致；场景对象可读取；回执没有私有 token；N 面板显示连接。连接成功不授权删除、覆盖、专家 Python 或最终导出。

## 7. Gatekeeper 与权限

先确认 Release 来源和 SHA-256，再处理 macOS 安全提示。不要删除 quarantine 属性、关闭 Gatekeeper 或运行来源不明脚本。Runtime 不应要求管理员权限、完全磁盘访问或公网监听。

## 8. 升级与卸载

升级：Revoke Access → 退出 MCP 客户端 → 校验新版 → 保留旧目录 → 安装新版 → 重启 Blender → 只读验收。失败时恢复旧版本。

卸载：Revoke Access → 在 Preferences 卸载 **PartMe Blender MCP** → 从客户端移除 `partme_blender` → 删除自行选择的 Runtime 目录。保留 `.blend`、输出和素材。

## 9. 排错

- `BLENDER_NOT_CONNECTED`：确认 N 面板已点击 Start MCP Server。
- 找不到 Add-on：重启 Blender，确认 ZIP 顶层为 `partme_blender_mcp/`。
- 找不到 Python：在客户端填写 `command -v python3` 返回的绝对路径。
- 多个 Blender：停止写操作并明确选择窗口，不能自动选最新会话。
