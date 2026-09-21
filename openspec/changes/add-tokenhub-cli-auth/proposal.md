# Change: 增加 TokenHub 独立认证与 3D 执行适配器

## Why

腾讯混元 3D 当前只支持腾讯云 `SecretId/SecretKey`。官方 TokenHub 同时提供 THCLI 浏览器 OAuth，以及由独立 API Key 鉴权的 3D HTTP API；二者职责不同，不能把 OAuth 状态误当成模型调用凭证。

## What Changes

- 为“腾讯混元 3D”增加独立的“TokenHub API Key”执行认证方式。
- 通过官方 `/v1/api/3d/submit` 与 `/query` 接入专业版、极速版并注册后续 3D 能力。
- 检测 `thcli` 安装与登录状态，使用退出码而不是界面文案判断授权是否可用。
- 从 Blender 启动 `thcli auth login`，保持回调进程存活并在完成后刷新供应商状态。
- 只保存非敏感的 profile、site 与状态；不读取或修改 `~/.thcli` 凭证文件。
- THCLI OAuth 仅作为账号和密钥管理助手；模型执行就绪只依据单独配置的 TokenHub API Key。

## Impact

- Affected specs: `hunyuan3d-tokenhub-auth`
- Affected code: Add-on preferences/panel, provider registry status, TokenHub CLI adapter, TokenHub 3D transport, capability registry, release packaging and tests
- External dependency: optional user-installed `tencent-tokenhub-cli`; Add-on 不自动安装
