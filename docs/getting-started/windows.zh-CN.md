# PartMe Blender MCP：Windows 安装手册

> 支持状态：**DOCUMENTED_NOT_RUN**  
> 适用：Windows 10/11 x64、Blender 4.2–5.2  
> 核验日期：2026-09-15

> **预发布提醒**：`v0.1.1` 是预发布版本。Windows 安装包已构建，但发布前必须等待 GitHub Windows CI 通过。

## 1. 下载

- 从 [Blender 官网](https://www.blender.org/download/)下载 Windows Installer。
- 下载 `partme-blender-mcp-addon-0.1.1.zip`。
- 下载 `partme-blender-mcp-runtime-0.1.1.zip` 和 `SHA256SUMS.txt`。

## 2. 校验 SHA-256

```powershell
Set-Location "$HOME\Downloads"
Get-FileHash .\partme-blender-mcp-addon-0.1.1.zip -Algorithm SHA256
Get-FileHash .\partme-blender-mcp-runtime-0.1.1.zip -Algorithm SHA256
```

结果必须与 `SHA256SUMS.txt` 一致。

## 3. 普通用户一键安装

1. 下载 `partme-blender-mcp-windows-x64-0.1.1.zip`。
2. 右键选择“全部解压”，不要直接在压缩包预览中运行。
3. 打开解压目录并阅读 `README-FIRST.txt`。
4. 双击 `install_partme_blender_mcp.bat`。
5. 看到 `Installed` 和 MCP 启动命令后关闭窗口。

熟悉 Python 的用户也可以运行：

```powershell
py -3.13 -m pip install .\partme-blender-mcp-windows-x64-0.1.1.zip
```

## 4. 检查 Python

```powershell
py -3 --version
py -3 -c "import sys; print(sys.executable)"
```

没有 `py` 时再运行 `python --version` 和 `where.exe python`。不要修改系统 Python。把 Runtime 解压到用户目录，例如 `%LOCALAPPDATA%\PartMe\BlenderMCP\`。

## 5. 安装 Blender Add-on

1. 打开 **Edit → Preferences → Add-ons**。
2. 右上角菜单选择 **从磁盘安装…**。
3. 选择 `partme-blender-mcp-addon-0.1.1.zip`，不要解压。
4. 搜索并启用 **PartMe Blender MCP**。
5. 返回 3D View，按 `N`。
6. 打开 **PartMe MCP**，选择输出/素材目录。
7. 点击 **Start MCP Server**。

Blender 用户配置通常位于 `%APPDATA%\Blender Foundation\Blender\<version>\`，不要直接复制到 Program Files。

## 6. Named Pipe 与安全软件

Windows 正式传输使用当前用户范围内的 **Named Pipe**，不是公网 TCP。正常安装不需要添加防火墙规则，也不要照搬其他 Blender MCP 项目的 9876 端口说明。

如果安全软件阻止 Runtime：核对来源和 SHA；只检查被阻止的明确文件；不要把整个目录加入排除列表。

## 7. 配置客户端

- [Codex](codex.zh-CN.md)
- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [通用 MCP](generic-mcp.zh-CN.md)
- [macOS](macos.zh-CN.md)

Windows 推荐命令 `py`，参数为 `-3 -m partme_blender_mcp`。若客户端只接受一个命令字段，填写 `py.exe` 的绝对路径，并将参数保留为独立参数。

## 8. 只读验收

```text
partme_blender
blender_connection_status
blender_scene_inspect
```

确认服务加载、场景对象可读且回执不含 token。当前 Windows 前台实机尚未执行，因此保持 **DOCUMENTED_NOT_RUN**。

## 9. 升级、回退与卸载

升级：Revoke Access → 关闭客户端 → 校验新版 → 备份旧 Runtime → 安装 → 重启 Blender → 只读验收。失败则恢复备份。

卸载：从 Blender 卸载 **PartMe Blender MCP**；从客户端删除 `partme_blender`；只删除 manifest 记录的 Runtime 文件。不要删除 `.blend`、渲染、导出和素材。
