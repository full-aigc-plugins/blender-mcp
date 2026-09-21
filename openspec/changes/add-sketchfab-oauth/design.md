# Design

OAuth 授权只接受显式端口的 `http://127.0.0.1` 或 `http://localhost` 回调，且必须与 Sketchfab 应用后台登记值完全一致。随机 `state` 在回调时校验；失败时不交换或保存 Token。

API Token 请求使用 `Authorization: Token ...`；OAuth 请求使用 `Authorization: Bearer ...`。三个资产能力共用同一认证头解析函数，避免不同路径行为漂移。

Client Secret、access token 和 refresh token 使用 Blender 密码属性保存，不写入 `.blend`、MCP 回执和诊断日志。真实授权需要用户自行在 Sketchfab 创建应用并把凭证填入 Blender。
