# PartMe Blender MCP

> 一个安全、可见、可恢复的 Blender MCP 运行时：用同一个 Add-on 连接 Codex、Claude、MiniMax Design、Cursor 和其他 MCP 客户端。

<p align="center"><img src="assets/brand/logo.png" alt="PartMe Blender MCP" width="144"></p>

[English](README.md) | [简体中文](README.zh-CN.md) · [安装中心](docs/getting-started/README.zh-CN.md) · [安全](SECURITY.md) · [架构规格](docs/superpowers/specs/2026-09-15-partme-blender-mcp-design.md)

![PartMe Blender MCP Hero](assets/brand/hero.png)

## 项目定位

PartMe Blender MCP 把标准 MCP `stdio` 请求转换为经过 Schema、事务、场景版本和路径策略保护的 Blender 操作。它不是文生 3D 模型，也不绑定某个 AI 客户端；它负责让已经连接的客户端可靠地创建、检查、动画化、渲染和导出 Blender 工程。

### 适合谁

- 希望通过自然语言操作 Blender，同时保留前台可见和人工接管的创作者；
- 需要让 Codex、Claude、MiniMax Design 或 Cursor 共用 Blender 能力的团队；
- 需要结构化工具、回滚、版本化交付和审计边界的自动化工程师。

### 解决什么问题

| 问题 | PartMe Blender MCP | 可验证入口 |
|:---|:---|:---|
| 客户端各自安装不同 Blender 插件 | 一个中性 Add-on + 标准 MCP Runtime | `partme_blender` |
| 任意 Python 难以审计 | 164 条闭合结构化 Blender 命令；不暴露专家 Python | `blender_capability_list` |
| 人工编辑可能被覆盖 | `sceneRevision`、事务和接管失效机制 | `blender_connection_status` |
| 导出失败后状态不清楚 | 快照、回滚、任务恢复和回执 | `blender_job_status` |
| 初次安装复杂 | 平台和客户端独立图文教程 | [安装中心](docs/getting-started/README.zh-CN.md) |

## 一眼看懂

```text
Codex / Claude / MiniMax Design / Cursor / Generic MCP
                         │  MCP 2025-06-18 · stdio
                         ▼
┌────────────────────────────────────────────────────────┐
│ PartMe Blender MCP                                     │
│ ① MCP 生命周期与分页工具目录                           │
│ ② 私有会话令牌、闭合 Schema、事务和 sceneRevision     │
│ ③ Blender 主线程执行、暂停/接管、快照与恢复            │
│ ④ 模型、动画、渲染、合成、视频与可验证导出             │
└────────────────────────────────────────────────────────┘
                         │ 私有 UDS / Named Pipe
                         ▼
                前台 Blender + PartMe MCP Add-on
```

![PartMe Blender MCP Architecture](assets/brand/architecture.png)

| 项目属性 | 值 |
|:---|:---|
| 产品 | PartMe Blender MCP |
| MCP Server ID | `partme_blender` |
| 当前版本 | `0.1.0` 预发布 |
| MCP 协议 | `2025-06-18` |
| Harness 兼容协议 | `codex-blender/v1` |
| Blender | 4.2–5.2，按真实验证矩阵声明 |
| Python | 3.11–3.13 |
| 传输 | stdio → macOS UDS / Windows Named Pipe |
| 许可证 | Apache-2.0 |

## 核心能力与边界

### 已实现

| 领域 | 能力 | 状态 |
|:---|:---|:---|
| 场景与建模 | 对象、集合、网格、曲线、修改器、硬表面配方 | 从上游 Harness 迁移，待新仓库真实 Blender 回归 |
| UV 与外观 | UV、PBR 材质、贴图、Geometry Nodes、烘焙 | 同上 |
| 角色与动画 | 骨架、蒙皮、约束、IK/FK、Action、F-Curve、NLA、形态键 | 同上 |
| 镜头与渲染 | 相机路径、手持响应、Eevee/Cycles、passes、合成 | 同上 |
| 模拟与编辑器 | 刚体、布料、软体、烟雾、Grease Pencil、Tracking、VSE | 同上 |
| 质量与交付 | 几何/动作/镜头检查、快照、后台任务、多格式导出 | 同上 |
| MCP | initialize、分页 tools/list、tools/call、structuredContent | 自动化测试覆盖 |

### 不负责

- 不生成故事、剧本或跨镜头制片计划；
- 不捆绑 Rodin、混元、即梦、Sketchfab 等供应商服务；
- 不静默下载 Blender、扩展、模型或素材；
- 不把连接成功等同于作品质量通过；
- 不把未完成真实客户端/平台验证的组合标为生产可用。

## 安装

### 1. 下载并安装 Blender

从 [Blender 官网](https://www.blender.org/download/)下载。打开一次并确认默认场景正常。

### 2. 下载 Release

从 [v0.1.0](https://github.com/partme-ai/blender-mcp/releases/tag/v0.1.0)下载：

```text
partme-blender-mcp-addon-0.1.0.zip
partme-blender-mcp-runtime-0.1.0.zip
SHA256SUMS.txt
```

先校验 SHA-256，再安装。

### 3. 安装 Runtime

```bash
python -m pip install ./partme-blender-mcp-runtime-0.1.0.zip
python -m partme_blender_mcp --help
```

也可使用平台包中的安装器：

- macOS：`install_partme_blender_mcp.command`
- Windows：`install_partme_blender_mcp.bat`

### 4. 安装 Blender Add-on

1. Blender → **Edit → Preferences → Add-ons**。
2. 右上角菜单 → **从磁盘安装…**。
3. 选择 `partme-blender-mcp-addon-0.1.0.zip`，不要解压。
4. 启用 **PartMe Blender MCP**。
5. 回到 3D View，按 `N`，打开 **PartMe MCP**。
6. 选择授权目录，点击 **Start MCP Server**。

![From Disk](docs/assets/reference/blender-install-from-disk.png)

### 5. 配置客户端

| 客户端 | 手册 |
|:---|:---|
| Codex | [codex.zh-CN.md](docs/getting-started/codex.zh-CN.md) |
| Claude Desktop | [claude-desktop.zh-CN.md](docs/getting-started/claude-desktop.zh-CN.md) |
| Claude Code | [claude-code.zh-CN.md](docs/getting-started/claude-code.zh-CN.md) |
| MiniMax Design | [minimax-design.zh-CN.md](docs/getting-started/minimax-design.zh-CN.md) |
| Cursor | [cursor.zh-CN.md](docs/getting-started/cursor.zh-CN.md) |
| 通用 MCP | [generic-mcp.zh-CN.md](docs/getting-started/generic-mcp.zh-CN.md) |
| macOS | [macos.zh-CN.md](docs/getting-started/macos.zh-CN.md) |
| Windows | [windows.zh-CN.md](docs/getting-started/windows.zh-CN.md) |

## 快速开始

配置示例：

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

新建客户端对话，先执行：

```text
调用 blender_connection_status。
连接成功后调用 blender_scene_inspect，只读列出当前场景。
```

通过后再要求创建对象。修改类工具需要事务；`v0.1.0` 不向通用 MCP Client 暴露授权签发工具，危险操作会被拒绝。

## 安全、事务与恢复

- 描述符拒绝符号链接和宽松权限；token 不进入 MCP 回执。
- macOS 使用私有 Unix Domain Socket；Windows 使用当前用户 Named Pipe。
- 修改命令携带最新 `sceneRevision`，防止覆盖人工操作。
- 一个 Blender 默认只有一个主动写入客户端。
- Pause/Take Over/Revoke 会使旧事务和授权失效。
- `v0.1.0` 对删除、覆盖、专家 Python 和受门禁的最终导出返回 `AUTHORIZATION_REQUIRED`；本地审批 UI 完成前不提供绕过入口。
- `annotations` 仅是客户端提示，Harness 才是权限事实源。

漏洞请使用 [GitHub Security Advisories](https://github.com/partme-ai/blender-mcp/security/advisories/new) 私下报告。

## 错误与排查

| 错误 | 含义 | 处理 |
|:---|:---|:---|
| `BLENDER_NOT_CONNECTED` | 没有活动 Harness | 在 N 面板点击 Start MCP Server |
| `AMBIGUOUS_SESSION` | 多个 Blender 会话 | 明确绑定目标窗口 |
| `STALE_SCENE_REVISION` | 场景已变化 | 重新检查并开启新事务 |
| `AUTHORIZATION_REQUIRED` | 危险操作没有可信授权 | `v0.1.0` 停止该操作，不允许客户端自行声称已确认 |
| 工具列表不完整 | 未读取全部分页 | 跟随 `nextCursor` |

## 开发、测试与发布

```bash
python -m unittest discover -s tests
python scripts/package_release.py --output dist
git diff --check
```

发布产物包括 Add-on、Runtime、macOS/Windows 包、`runtime-manifest.json`、`SHA256SUMS.txt` 和 `SBOM.spdx.json`。GitHub tag `v*` 触发预发布工作流。

## 项目结构

```text
blender-mcp/
├── src/partme_blender_mcp/     # stdio MCP Runtime 与 Harness
├── addon/partme_blender_mcp/   # Blender Add-on
├── installers/                 # macOS / Windows 用户级安装器
├── scripts/package_release.py  # 可重复发行构建
├── docs/getting-started/       # 八份客户端/平台图文手册
├── assets/brand/               # Logo、Hero、Cover、内容图
└── tests/                      # 文档、协议与发行契约
```

## 兼容与迁移

`0.1.0` 是预发布版本。Harness 暂时保留 `codex-blender/v1`，使现有 `codex-blender-plugin` 能进行差分迁移；新公共身份、MCP Server ID 和 Add-on 均使用 PartMe。未经验证的客户端保持 `DOCUMENTED_NOT_RUN`。

## 深入文档

- [跨客户端架构设计](docs/superpowers/specs/2026-09-15-partme-blender-mcp-design.md)
- [图文安装中心](docs/getting-started/README.zh-CN.md)
- [v0.1.0 安全审查](docs/verification/security-review-0.1.0.md)
- [v0.1.0 许可证工程分诊](docs/verification/license-compliance-0.1.0.md)
- [品牌资产与生成来源](assets/brand/README.md)

## 贡献与许可证

提交变更时必须附带对应测试和兼容证据，不能扩大默认权限或将供应商功能混入核心。

本项目采用 [Apache-2.0](LICENSE)。
