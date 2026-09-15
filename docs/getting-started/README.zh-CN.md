# PartMe Blender MCP 图文安装中心

> 当前阶段：**预发布文档**  
> Runtime Release：`v0.1.0` 预发布
> 文档核验日期：2026-09-15

PartMe Blender MCP 让多个 MCP 客户端通过同一个安全 Harness 操作 Blender。完整安装永远分两步：

```mermaid
flowchart LR
    A[安装 Blender 与 PartMe Add-on] --> B[N 面板 Start MCP Server]
    B --> C[安装 Runtime]
    C --> D[配置 MCP Client]
    D --> E[只读连接验证]
    E --> F[开始建模/动画/导出]
```

## 先选择操作系统

| 系统 | 手册 | 当前证据 |
|---|---|---|
| macOS Apple Silicon / Intel | [macOS](macos.zh-CN.md) | 包构建、Runtime 安装、Blender 5.2.1 Add-on 安装 **VERIFIED** |
| Windows 10/11 x64 | [Windows](windows.zh-CN.md) | **DOCUMENTED_NOT_RUN** |

## 再选择 MCP 客户端

| 客户端 | 手册 | 配置方式 | 当前证据 |
|---|---|---|---|
| Codex | [Codex](codex.zh-CN.md) | `codex mcp add` / Codex 插件 | CLI 语法 **VERIFIED** |
| Claude Desktop | [Claude Desktop](claude-desktop.zh-CN.md) | DXT / 本地开发 MCP | **DOCUMENTED_NOT_RUN** |
| Claude Code | [Claude Code](claude-code.zh-CN.md) | `claude mcp add --transport stdio` | **DOCUMENTED_NOT_RUN** |
| MiniMax Design | [MiniMax Design](minimax-design.zh-CN.md) | 添加自定义连接器 | UI 已观察，握手 **DOCUMENTED_NOT_RUN** |
| Cursor | [Cursor](cursor.zh-CN.md) | 全局或项目 `mcp.json` | **DOCUMENTED_NOT_RUN** |
| 其他客户端 | [通用 MCP](generic-mcp.zh-CN.md) | 标准 stdio | **DOCUMENTED_NOT_RUN** |

## 下载

正式发行后只从：

- [GitHub Releases](https://github.com/partme-ai/blender-mcp/releases/latest)
- [Blender 官网](https://www.blender.org/download/)

下载文件：

```text
partme-blender-mcp-addon-0.1.0.zip
partme-blender-mcp-runtime-0.1.0.zip
SHA256SUMS.txt
```

安装前必须核对 Release 中的 `SHA256SUMS.txt`；预发布不等于生产就绪。

## 所有客户端共同验收

服务名：

```text
partme_blender
```

先调用：

```text
blender_connection_status
blender_scene_inspect
```

两条都通过后，才开始写操作。不要用社区 **MCP for Blender** 的连接状态替代 PartMe Harness 验收。

## 图片说明

当前图片来自用户提供的 Blender 5.2.1 和 MiniMax Design 界面。社区 Add-on 截图仅用于定位 Add-ons 页面；PartMe Add-on 实现后必须补拍正式启用页和 N 面板 Start MCP Server。
