# PartMe Blender MCP 供应商整合设计

> 状态：已确认实施  
> 目标版本：`blender-mcp 0.5.0` / `blender-design 0.10.0`
> 前置基线：已发布的 `blender-mcp 0.2.1` 不覆盖、不重传同名资产

## 1. 目标

在不削弱 PartMe Harness 安全边界的前提下，吸收社区 Blender MCP 的资产库与 AI 三维生成能力：

- `blender-mcp` 提供供应商注册表、状态协议、通用 Blender 子面板与受控导入闭环；
- `blender-design-plugin` 提供社区供应商目录、安装适配和 MCP 宿主扩展；
- Poly Pizza 只保留 PartMe 原生命令为主路径；
- 社区搜索、下载、生成、导入具有不同风险级别；
- 下载与生成结果必须落入授权素材目录，再通过 Harness 事务导入并返回回执；
- 社区 Add-on 仍是可选 sidecar，不成为第二个 PartMe 连接或授权入口。

## 2. 非目标

- 不把供应商密钥写入 `.blend`、Scene 自定义属性或 MCP 返回值；
- 不允许社区 `execute_code`、任意 URL、任意文件路径绕过 Harness；
- 不把供应商可用状态等同于已付费、已授权或生产验收通过；
- 不覆盖已经发布的 `v0.2.1` Release 资产；
- 不用静态截图代替真实 Blender 和客户端验收。

## 3. 分层与所有权

```mermaid
flowchart TB
    UI[PartMe Blender MCP 通用子面板]
    PR[ProviderRegistry + partme-provider-status/v1]
    H[PartMe Harness]
    N[原生资产命令]
    P[blender-design-plugin 供应商目录]
    C[社区 Add-on localhost:9876]
    E[外部资产/生成服务]

    UI --> PR
    P --> PR
    PR --> H
    H --> N
    H --> C
    C --> E
    E -->|下载到授权素材目录| H
    H -->|事务导入 + sceneRevision + receipt| UI
```

`blender-mcp` 是协议、UI 和安全编排事实源；`blender-design-plugin` 只贡献供应商描述和宿主适配。

## 4. 供应商协议

状态对象使用 `partme-provider-status/v1`：

```json
{
  "schemaVersion": "partme-provider-status/v1",
  "providerId": "sketchfab",
  "category": "asset_library",
  "source": "community",
  "enabled": false,
  "mutable": true,
  "configurable": true,
  "toggleLocked": true,
  "state": "configuration_required",
  "label": "Sketchfab",
  "statusText": "需要配置",
  "risks": ["read", "network_download", "scene_import"],
  "actions": ["configure"]
}
```

合法类别：

- `asset_library`
- `ai_model`

合法状态：

- `ready`
- `disabled`
- `configuration_required`
- `unavailable`
- `busy`
- `error`

合法风险：

- `read`
- `network_download`
- `paid_generation`
- `scene_import`
- `external_export`

注册表拒绝重复 ID、未知类别/状态/风险和包含 `apiKey`、`token`、`secret`、`password` 的公开元数据。

`enabled`是用户偏好，`state`是运行事实，两者必须独立。只有`enabled = true`且状态为`ready`或`busy`的供应商计入
`供应商可用`并进入自动路由。本地素材库固定启用；外部供应商可以启停。配置缺失时开关禁用，任务运行时开关锁定，
用户必须通过独立的终止动作结束任务。供应商启用偏好保存在 Blender 用户配置中，不写入`.blend`；社区供应商同时把
偏好同步到其真实`blendermcp_use_*`运行属性。临时离线或状态探测错误不得清除用户偏好；开关可以保持启用，但调用仍由
路由门禁以`PROVIDER_UNAVAILABLE`拒绝，待供应商恢复后自动重新进入候选集。

## 5. UI

视觉与交互定稿见：[PartMe Blender MCP 侧栏界面设计 V1](../../design/partme-blender-mcp-sidebar-ui-v1.md)。

在 `PartMe MCP` 页签下只注册一个工作台面板。顶部显示服务状态、场景版本、供应商可用数和刷新/执行设置；内容通过
`制作`、`素材`、`模型`、`接入`四个原生 Tab 切换，默认显示`制作`。旧权限、素材、模型、制作过程子面板不再并排注册。

供应商行显示图标、名称、文字状态和必要动作；不得只用颜色或复选框表达状态。`PartMe 制作过程`
继续显示实时任务、审批、接管、撤销、视图与播放控制。

供应商行显示图标、名称、文字状态、必要动作和真实启用开关。本地素材库显示`始终启用`。配置按钮必须打开对应供应商
设置；不得仅报告环境变量或打开无定位的空白偏好页。原有相机、正面、侧面、顶面、播放/暂停和帧定位快捷操作必须保留。

## 6. Poly Pizza 单路径

- 公共能力只暴露 `asset.polypizza_search` 与 `asset.polypizza_download`；
- 社区桥不再允许 `get_polypizza_status`、`search_polypizza_models`、`download_polypizza_model`；
- 下载写入授权素材根下的 `polypizza/<modelId>/`，同时写入许可证 sidecar；
- 下载完成不自动修改场景，导入必须另行调用 `asset.import_file`。

## 7. 风险和导入闭环

| 动作 | 风险 | 规则 |
|---|---|---|
| 状态、分类、搜索、轮询 | `read` | 不修改场景，不写文件 |
| 下载资产/生成结果 | `network_download` | 仅写授权素材目录，限制主机、后缀和大小 |
| 提交 Rodin/混元生成 | `paid_generation` | 已授权预算内默认自动；未授权或超出预算时形成 Blender 本地待审批项 |
| 导入模型/设置贴图 | `scene_import` | 必须使用事务和最新 `sceneRevision` |
| 外部导出 | `external_export` | 延续 Harness 本地审批 |

社区的直接 `import_generated_asset*` 不再作为插件公共主路径。生成服务返回 URL 或文件后，宿主先下载到授权目录，
再调用 PartMe 的 `asset.import_file`，由 Harness 生成 changedObjects、sceneRevision、快照和回执。

进行中的生成任务必须可终止。终止至少停止本地轮询、下载和后续导入；供应商支持取消接口时同时取消远端任务，
不支持时必须明确提示远端任务可能仍在运行。`终止生成`不等同于暂停整个制作会话或撤销 MCP 连接。

## 8. 版本与兼容

- `v0.2.1` 已发布，先记录其版本漂移基线，不修改远端资产；
- 本增量使用 `blender-mcp 0.5.0`；
- 插件使用 `blender-design 0.10.0`，锁定新的 runtime/add-on/community SHA；
- 旧 `blender_community_call` 保留一个版本，但对已移除的 Poly Pizza 和直接导入命令返回结构化迁移错误；
- `scripts/harness/` 暂不删除，建立带 SHA 的差分门禁并声明只读兼容边界。

## 9. 验收

- 供应商注册表与状态协议单元测试通过；
- 单工作台四 Tab 在窄宽度下不截断关键状态，默认显示制作；
- 外部供应商开关真实控制社区 handler/PartMe 原生命令路由，配置缺失和 busy 状态不可误切；
- 配置入口定向打开对应 Add-on Preferences，密钥不进入 Scene、状态、日志或回执；
- 原有视图与播放快捷操作保留；
- 自动生成在已授权预算内不中断制作，并提供语义准确的终止操作；
- Poly Pizza 公共路径只有 PartMe 原生命令；
- 插件扩展工具跨页只出现一次；
- 版本、README、Add-on 元数据、producer 与发布包一致；
- 新发布包可复现构建，SHA/manifest/SBOM 一致；
- 真实 Blender 验证折叠、缺密钥、错误、busy、审批和导入回执；
- Codex、ZCode、Kimi、Windows 结果分别记录为 `PASS`、`FAIL` 或 `NOT_RUN`，不得互相替代。
