# 腾讯混元 3D 能力扩展验证（2026-09-21）

## 验证范围

- 模型卡保持显示“腾讯混元 3D”。
- 配置入口显示“腾讯云 API 凭证”，并提供 `SecretId`、`SecretKey`、账户区域、服务类型和任务类型。
- 任务类型提供“专业版”和“极速版”。
- 专业版、极速版分别解析为独立的 Submit/Query Action；不支持的账户区域/服务/能力组合在网络请求前拒绝。
- TokenHub 未加入当前认证适配器列表，不与腾讯云 API 凭证共用配置。
- 付费生成沿用费用预算、审批、可终止任务、授权目录、事务导入与回执链路。
- API 传输改用腾讯云官方 Python SDK，不再由业务层手写 TC3 签名或逐行 HTTP 请求。
- Add-on 发布包私有携带固定版本的 AI3D/common SDK；运行时不执行 `pip install`，也不污染 Blender 全局 Python 环境。

## 自动化证据

```text
python3 -m unittest discover -s tests -p 'test_*.py'
Ran 213 tests
OK (skipped=5)

openspec validate extend-hunyuan3d-capabilities --strict
Change 'extend-hunyuan3d-capabilities' is valid
```

## 真实 Blender 证据

- Blender：5.2.1 LTS。
- 安装包：`partme-blender-mcp-addon-0.5.3.zip`。
- 源码与已安装的 `panel.py`、`provider_engine.py`、`hunyuan_capabilities.py` SHA-256 一致。
- Add-on 在当前 Blender 中完成禁用、模块清理、重新启用和连接器重启。
- 发布包包含 `_vendor/tencentcloud/ai3d/v20250513/ai3d_client.py`、`_vendor/tencentcloud/common/credential.py`、SDK 许可证和来源清单。
- Blender Python 控制台真实执行 `_load_sdk()`，输出 `SDK_OK tencentcloud.ai3d.v20250513.ai3d_client tencentcloud.common.common_client`。
- 模型页真实显示单一“腾讯混元 3D”卡片；配置弹窗真实显示“腾讯云 API 凭证”、五项配置字段以及“专业版 / 极速版”下拉选项。
- MCP 连接状态返回 `connected: true`，场景版本为 0，待审批数为 0，累计下游费用为 0。

## SDK 事实源

- 腾讯云公共参数：服务名 `ai3d`、地域 `ap-guangzhou`、TC3-HMAC-SHA256。
- 腾讯云 API 概览：专业版、极速版及纹理、减面、组件、UV、动作、自动绑骨、格式转换等独立 Action。
- Python 包固定为 `tencentcloud-sdk-python-ai3d==3.1.57` 与 `tencentcloud-sdk-python-common==3.1.57`；归档中的 `PROVENANCE.md` 记录来源与 SHA-256。

## 有意保留的验证边界

本轮没有填写真实 `SecretId`/`SecretKey`，也没有提交付费生成任务，因此没有产生费用。真实服务端生成、供应商计费回执和生成文件导入，需要用户在 Blender 中完成腾讯云凭证配置并明确单次费用上限后再执行。
