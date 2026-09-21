## Context

见 [proposal.md](proposal.md)。现有 `preview.capture` 已会恢复 Blender 渲染状态并生成里程碑回执，但没有单帧截图、目标锁定、视觉评分状态，也没有为远程 MCP 返回图片内容。Harness 已有事务、场景版本、授权目录和官方 MCP SDK 传输，因此视觉闭环应复用这些边界。

## Goals / Non-Goals

**Goals:**

- 把视觉证据、目标锁定和 Judge 状态建成 Runtime 能力，而非某个客户端脚本。
- 保持截图为场景只读操作，同时明确其授权目录写入副作用。
- 允许 stdio、HTTP 和 SSE 客户端得到相同图片内容与结构化回执。
- 让事务控制保持显式，使 Judge 后的 commit/rollback 可审计。

**Non-Goals:**

- 本变更不直接复制 Dream Loop 仓库、不内置 Fal、不替换既有 ProviderAdapter。
- 本变更不自动调用视觉模型；VisualVerdict 由人工或客户端 Judge 产生。
- 本变更不宣称未实际执行的真实付费、客户端或 Windows 验收。

## Decisions

### 1. 截图使用不可覆盖的授权相对路径

`scene.screenshot` 只接受相对路径，解析到 `approved_output_root` 内；已存在文件一律失败。这样避免把“只读场景命令”变成任意文件覆盖能力。替代方案是增加 `overwrite` 审批，但会让同一个工具的风险随参数变化并使客户端注解失真。

### 2. 回执包含内容身份，MCP 再验证后附加图片块

Harness 返回路径、哈希、字节数和尺寸；MCP 适配器仅对已知视觉命令读取该路径，并再次检查授权根、大小和 SHA-256，然后追加 MCP `image` 内容块。这样本地 Harness 不承担协议编码，远程客户端也不依赖共享文件系统。

### 3. 视觉循环是持久状态机，不是自动执行器

循环状态写入 `<output>/visual-loops/<loopId>/state.json`，写入采用临时文件后原子替换。状态机管理目标、轮次、评审、最佳分和停滞；具体建模修改、视觉模型调用和 transaction 命令由客户端编排。与把 Agent 循环嵌入 Blender 主线程相比，这能避免 UI 阻塞，并兼容无子智能体客户端。

### 4. 事务动作是建议而非隐式副作用

`record_verdict` 返回 `recommendedAction`，但不调用 commit/rollback。接受时建议 commit；停滞、耗尽或取消时建议 rollback；其余建议 revise。客户端必须在评审后显式提交，保留现有授权、回执和幂等语义。

### 5. VisualVerdict 使用固定首版维度

首版固定为 composition、lighting、materials、details 四项，运行时计算算术平均总分。问题与建议是有界文本数组。未来新增维度需要版本化 schema，避免历史分数口径漂移。

### 6. 会话描述符是 Add-on/Runtime 契约握手

Add-on 写入 `runtimeVersion`、`harnessProtocolVersion`、排序命令清单和内容哈希。Runtime 必须在连接状态检查和每次工具转发前验证。不做“遇到 UNKNOWN_COMMAND 再猜版本”的事后兼容，因为那会导致工具目录表面可用、实际不可用。

### 7. 对象定位器使用命令级 Schema

保留历史通用 `object` 字段的字符串定义，避免改变仍使用对象名的其他命令；仅对调用 `ObjectResolver` 的质量检查命令用 `COMMAND_FIELD_SCHEMAS` 覆盖成结构化定位器。

## Risks / Trade-offs

- [Base64 图片增加 MCP 响应体积] → 对输入和输出设置硬上限；超限只返回结构化回执和明确错误，不悄悄截断。
- [图片路径与读取之间发生替换] → MCP 返回前重算哈希并与回执比对。
- [客户端忘记按建议提交或回滚] → 状态明确暴露 `recommendedAction` 与待处理事务 ID；Skill 将其作为强制步骤。
- [Blender 异常中断留下临时文件] → 目标上传和状态持久化都先写 `.part`，成功校验后原子替换。
- [自动 Judge 的模型差异] → Runtime 不绑定模型，只验证统一 VisualVerdict 契约并保存来源元数据。

## Migration Plan

1. 在开发树完成规范、目标测试和 Runtime 实现。
2. 在真实 Blender 验证截图状态恢复、失败恢复、窄路径和远程图片返回。
3. 发布新的不可变 `blender-mcp` RC，并验证发布包与三个传输。
4. 更新 `blender-design-plugin/runtime.lock.json`，再新增 `blender-visual-loop` Skill 和客户端策略。
5. 若出现回归，插件回退到旧锁定 Runtime；视觉循环状态文件保留但不被旧版读取。
