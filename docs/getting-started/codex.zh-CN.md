# PartMe Blender MCP：Codex 操作手册

> 客户端状态：**VERIFIED**（本机 `codex mcp` 配置语法）  
> Runtime/独立仓库状态：预发布  
> 核验日期：2026-09-15

## 1. 先完成平台安装

先安装 Blender、Runtime 和 Add-on：

- [macOS 安装](macos.zh-CN.md)
- [Windows 安装](windows.zh-CN.md)

必须在 Blender 的 **PartMe MCP** 页签点击 **Start MCP Server**。安装 Codex MCP 配置不能代替 Blender 端连接。

## 2. 两种使用方式

### 方式 A：随 Codex 插件提供

未来 `codex-blender-plugin` 会锁定经过验证的 PartMe Blender MCP Runtime。安装该插件后，MCP Server 会随插件启用。这个兼容适配尚未从旧仓库迁移完成。

### 方式 B：独立 Runtime

Runtime 可执行后，注册用户级本地 stdio 服务：

```bash
codex mcp add partme_blender -- python -m partme_blender_mcp
codex mcp list
codex mcp get partme_blender
```

`--` 后面是实际启动命令和参数。macOS 如果 `python` 不存在，改用 `command -v python3` 的结果；Windows 可使用 `py -3 -m partme_blender_mcp`。

## 3. 让新任务加载工具

添加或升级 MCP 后，新建一个 Codex 任务。已有任务不会可靠地热加载新的工具目录。

预期工具采用单下划线：

```text
blender_connection_status
blender_scene_inspect
blender_object_create_mesh
blender_animation_pose_keyframe
```

## 4. 第一次验证

先告诉 Codex：

```text
调用 partme_blender 的 blender_connection_status，只读检查 Blender 是否连接。
连接成功后调用 blender_scene_inspect，列出当前场景，不修改任何对象。
```

通过条件：

- `partme_blender` 为 enabled；
- `blender_connection_status` 返回一个活动 Harness；
- `blender_scene_inspect` 返回当前 Blender 场景；
- 没有双下划线工具名；
- 没有 token 出现在响应中。

## 5. 开始制作

只读验证通过后，再提出建模任务。修改操作必须使用事务和最新 scene revision；`v0.1.0` 会拒绝删除、覆盖、专家 Python 与受门禁最终导出，且不提供 MCP 授权签发工具。不要开启 Codex auto-run 试图绕过门禁。

## 6. 排错

```bash
codex mcp list
codex mcp get partme_blender
python -m partme_blender_mcp doctor --json
```

- 找不到模块：Runtime 尚未安装到该 Python。
- 服务存在但 Blender 未连接：在 N 面板点击 Start MCP Server。
- 多窗口冲突：明确选择一个 Blender，不要反复重试。
- 工具仍是旧名：新建任务并确认加载的 Runtime 版本。

## 7. 移除

```bash
codex mcp remove partme_blender
```

随后在 Blender 点击 **Revoke Access**。移除 MCP 配置不会删除 Blender 工程或导出文件。

## 8. 其他客户端

- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [通用 MCP](generic-mcp.zh-CN.md)
