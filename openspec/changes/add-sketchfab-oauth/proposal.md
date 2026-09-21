# Change: 增加 Sketchfab OAuth 2.0 授权

## Why

Sketchfab 官方同时支持静态 API Token 与 OAuth 2.0。现有插件只有 API Token，无法为希望使用浏览器授权的账户提供完整授权、回调和 Bearer Token 调用链。

## What Changes

- Sketchfab 配置增加 API Token 与 OAuth 2.0 两种模式。
- OAuth 模式配置 Client ID、Client Secret 和已注册的本机回调地址。
- 使用 authorization-code flow、随机 state、本机回调与居中完成页。
- 搜索、预览和下载统一根据模式发送 `Token` 或 `Bearer` 请求头。
- 授权完成前供应商保持不可用；不在日志、回执或界面中显示 Token。

## Impact

- Affected specs: `sketchfab-oauth`
- Affected code: Blender preferences/panel, OAuth callback adapter, provider status and Sketchfab requests
