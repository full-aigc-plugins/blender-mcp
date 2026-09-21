## Purpose

为 Blender 自动设计提供持久、可审计的视觉迭代状态，使人工或智能体 Judge 都能在事务提交前作出一致决定，并在无子智能体客户端中继续运行。

## ADDED Requirements

### Requirement: 视觉循环必须持久化轮次状态
运行时 SHALL 提供创建、查询、记录截图、记录评审和取消命令，并在授权输出目录中以原子写入持久化循环状态。

#### Scenario: 创建后恢复状态
- **WHEN** 客户端创建循环后重新连接 Blender
- **THEN** `visual_loop.status` 返回相同目标哈希、配置、历史和当前状态

#### Scenario: 取消循环
- **WHEN** 客户端取消活动循环
- **THEN** 循环进入终态且后续不得记录新截图或评审

### Requirement: VisualVerdict 必须结构化
每个评审 SHALL 包含构图、光照、材质、细节四项 0 到 10 分、总分、问题列表和下一步建议；总分必须由运行时按四项平均值计算，不信任客户端提供的总分。

#### Scenario: 有效评审
- **WHEN** 客户端为当前轮次提交四项合法分数和建议
- **THEN** 运行时保存规范化 VisualVerdict 并更新最佳轮次与推荐事务动作

#### Scenario: 无效评分
- **WHEN** 任一评分越界、缺失或不是数值
- **THEN** 运行时拒绝整个评审且不改变历史

### Requirement: Judge 必须先于事务提交
视觉循环 SHALL 只根据阈值输出 `commit`、`rollback` 或 `revise` 建议，不得隐式调用场景提交或回滚；客户端必须在收到评审后显式执行 transaction 命令。

#### Scenario: 达到接受阈值
- **WHEN** 当前总分达到循环的最低接受分
- **THEN** 状态为 `accepted` 且推荐动作是 `commit`

#### Scenario: 未达到阈值且尚可继续
- **WHEN** 当前总分低于阈值且未达到停滞或轮次上限
- **THEN** 状态保持 `active` 且推荐动作是 `revise`

#### Scenario: 停滞或轮次耗尽
- **WHEN** 最佳分数在配置窗口内没有达到最小提升，或达到最大轮次
- **THEN** 循环进入 `stalled` 或 `exhausted`，推荐动作是 `rollback`

### Requirement: 编排不得依赖子智能体
运行时契约 SHALL 对单一客户端和多智能体客户端保持一致；是否把修改、截图和 Judge 分派给子智能体由客户端 Skill 决定。

#### Scenario: 无子智能体客户端
- **WHEN** 客户端不能创建子智能体
- **THEN** 同一客户端可顺序调用全部视觉循环命令并获得相同状态转移
