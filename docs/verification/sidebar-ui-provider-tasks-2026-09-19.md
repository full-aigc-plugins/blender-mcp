# Blender 侧栏与供应商任务验证（2026-09-19）

## 验证对象

- 源码版本：`0.4.0`
- 产物：`partme-blender-mcp-addon-0.4.0.zip`
- Add-on SHA-256：`a6794ff8e0487d342e743b6b06f631053ed555cf388d8ae9152c707151157d86`
- Blender：`5.2.1 LTS`
- 平台：macOS Apple Silicon

## 已通过门禁

| 门禁 | 结果 | 证据摘要 |
|---|---|---|
| 核心单元与分发测试 | PASS | `78 tests`，另有 `test_release_distribution` 的 `10 tests` 通过 |
| 插件完整回归 | PASS | `459 tests`，`1 skipped`（平台限定） |
| 打包内容 | PASS | Add-on 内含 `provider_registry.py`、`provider_tasks.py` 和新版 `panel.py` |
| 真实 Blender 加载 | PASS | 打包 Add-on 在 Blender 5.2.1 中启用并注册主面板与三个子面板 |
| 默认展开 | PASS | 权限、资产、AI 三个子面板均未声明 `DEFAULT_CLOSED` |
| 默认素材策略 | PASS | `auto_search_generate` |
| 生成终止 | PASS | 本地状态转为 `cancelled`；无远端取消 API 时 `remoteMayContinue=true` |
| 审批与事务 | PASS | 一次批准、拒绝、事务回滚、接管后重检均通过 |

真实 Blender 命令使用隔离配置，从发布 ZIP 解压后的 Add-on 目录直接加载：

```bash
BLENDER_USER_CONFIG=<isolated>/config \
BLENDER_USER_SCRIPTS=<isolated>/scripts \
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --python-exit-code 1 \
  --python tests/runtime/addon_and_approval_smoke.py -- <isolated>/addon
```

关键机器可读结果：

```json
{
  "providerPanelsRegistered": true,
  "providerPanelsDefaultOpen": true,
  "assetStrategyDefault": "auto_search_generate",
  "providerCancelResult": ["FINISHED"],
  "providerCancelled": true,
  "providerRemoteMayContinue": true,
  "addonEnabled": true,
  "sessionStarted": true,
  "descriptorMode": "0o600",
  "deleteRefused": "AUTHORIZATION_REQUIRED",
  "rollbackGated": "succeeded"
}
```

## 仍需单独记录的视觉验收

上述运行是打包产物的真实 Blender 行为验证，但以 headless 方式执行，不替代像素级视觉审查。
窄侧栏文字截断、不同系统缩放下的间距，以及绿色/琥珀/蓝色/红色在用户主题中的最终效果，
需要以前台截图补充；Blender Python UI 使用当前主题的原生颜色，不能硬编码 Web 风格 RGB。

当前社区 Add-on 没有 Rodin/混元的远端取消接口。因此 `终止生成`可以保证停止 PartMe
继续轮询、下载和导入，但只能明确提示远端任务可能继续，不能宣称第三方任务已被取消。
