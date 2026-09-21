## Why

腾讯混元 3D 当前只以一个布尔账户开关和专业版提交/查询动作接入，无法准确表达腾讯云 API 凭证、账户区域、服务类型和持续扩展的模型能力。官方 API 已同时提供专业版、极速版及多种后处理能力，需要在保持付费审批、取消、授权目录和事务导入边界的前提下建立稳定的扩展契约。

## What Changes

- 模型卡继续以“腾讯混元 3D”作为唯一供应商身份，配置入口明确标注“腾讯云 API 凭证”。
- 配置页提供 SecretId、SecretKey、账户区域和服务类型；传统腾讯云 API 凭证与未来 TokenHub 认证完全隔离。
- 首批开放专业版和极速版任务类型，并为每种类型声明独立的提交、查询、结果解析和能力元数据。
- 新增混元能力注册表，使纹理、拓扑、组件、UV、动作、绑骨、人物和格式转换可以独立扩展，而不继续堆叠条件分支。
- 所有付费提交继续进入 `paid_generation` 策略；取消、授权素材读取、受控下载、事务导入和执行回执沿用现有门禁。
- 不自动迁移、复用或混填 TokenHub 凭证；TokenHub 仅保留为未来独立认证适配器边界。

## Capabilities

### New Capabilities

- `hunyuan3d-provider`: 定义腾讯混元 3D 的配置、能力注册、任务类型、风险门禁、取消、结果暂存及事务导入行为。

### Modified Capabilities

无。

## Impact

- Blender Add-on 的供应商首选项、模型卡与配置弹窗。
- 混元 API profile、签名提交、任务轮询、结果解析和供应商任务注册。
- MCP 供应商命令输入模式、风险元数据和测试 fixture。
- 使用腾讯云官方 `tencentcloud-sdk-python-ai3d` 与 common SDK 承担 TC3 签名、请求模型和响应反序列化；Add-on 发布包携带经固定版本审计的 SDK 源码，避免要求 Blender 用户手工安装。
- 不改变 Hyper3D、资产供应商或 TokenHub 的现有行为。
