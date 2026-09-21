# TokenHub OAuth 与 3D API Key 验证（2026-09-21）

## 已实现

- “腾讯混元 3D”配置提供独立的“腾讯云 API 凭证 / TokenHub API Key”执行认证方式。
- THCLI OAuth 只辅助账号与密钥管理；TokenHub API Key 是独立的模型调用凭证。
- CLI 检测使用 `thcli` 可执行文件；授权判断使用 `thcli --profile ... --site ... --json auth status` 的退出码。
- 浏览器授权由后台 `thcli auth login` 进程持有 loopback 回调，日志权限为 0600。
- Add-on 不读取、修改或复制 `~/.thcli` 下的凭证、access token 或 refresh token。
- TokenHub 生成与查询使用官方 `/v1/api/3d/submit`、`/query`，Bearer Key 不进入任务参数、回执、日志或复制地址。
- 能力注册表覆盖专业版、极速版、组件、格式、纹理、UV、拓扑、绑骨、动作及两种 Polygen 减面模型。
- 未配置 API Key 时，即使 THCLI OAuth 已授权，供应商仍显示“需要配置 TokenHub API Key”。

## 自动化证据

```text
python3 -m unittest discover -s tests -p 'test_*.py'
Ran 223 tests
OK

openspec validate add-tokenhub-cli-auth --strict
Change 'add-tokenhub-cli-auth' is valid
```

## 真实 Blender 证据

- Blender：5.2.1 LTS。
- 已重新打包并安装 `partme-blender-mcp-addon-0.5.3.zip`，归档包含 `tokenhub_3d.py`。
- Blender 5.2.1 LTS 后台原生加载输出：`TOKENHUB_3D_NATIVE True ['TENCENT_CLOUD_API', 'TOKENHUB_API_KEY']`。
- Blender 原生模块与操作注册输出：`TOKENHUB_NATIVE https://tokenhub.tencentmaas.com/v1/api/3d True`。
- 以上证明独立 Key 属性、认证枚举、官方端点模块与 THCLI OAuth 操作已进入安装态；未证明真实远端 Key 有效。

## 当前边界

- 本机没有真实 TokenHub API Key，本轮也未获得付费调用额度批准，因此没有发起真实生成。
- 当前 UI 暴露专业版与极速版；其余能力已注册，后续以独立参数表单逐项开放。
- 当前环境未安装 THCLI；手动配置 TokenHub API Key 的执行路径不依赖 THCLI。
