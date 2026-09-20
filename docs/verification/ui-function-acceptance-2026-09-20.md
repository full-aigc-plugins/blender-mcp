# 界面与功能收尾验收（2026-09-20）

## 状态：未达到全能力、全平台或发布验收完成

### 2026-09-21 发布与当前运行态复核

- `blender-mcp 0.5.2` 与 `blender-design 0.11.2` 已正式发布；插件 `runtime.lock.json` 已锁定 0.5.2 Add-on/Runtime 及其 SHA-256，中央市场 Blender 条目已同步。当前 Codex 安装缓存为 0.11.2，Blender 5.2 磁盘 Add-on 为 0.5.2。
- 0.5.2 Runtime 全量 199 项测试通过；隔离 Blender 5.2.1 使用官方 SDK 完成 stdio 握手，目录为 178 个工具、4 页，并通过读、事务写、审批拒绝/批准重试、提交和回滚。
- 当前前台 Blender 进程及其 HTTP/SSE 子进程仍加载 0.5.1，若干 ZCode 存量进程仍加载 0.11.1。为保护未确认保存的场景，本轮未强制重启；因此不能用磁盘 0.5.2 代替当前窗口的 UI 与运行态验收。
- Hyper3D 保持客户端 OAuth，不把 OAuth Token 写入 Blender。新建 Codex 只读会话在初始化阶段仍记录 HTTP 202 空响应缺少 `Content-Type` 的兼容告警，但重试后成功调用 `rodin_get_status`，得到预期的“Generation was not found”，并由客户端列出 7 个工具；未调用生成或变更工具。当前结论改为“OAuth 已授权且可重试连接，仍有初始化兼容告警”，不再沿用“完全连接失败”。
- 仍未完成：前台 Blender 保存后重启与四 Tab 实屏复核、0.11.2 的 ZCode/Kimi 新进程验收、Windows 当前版本验收，以及需要真实凭证/预算的供应商生成到事务导入链。

### 最新增量：复制按钮与无效轮询响应

- 地址行取消固定 90:10 分栏，为“复制”预留 3 UI units；源码及安装文件已更新，8 项布局测试通过。待用户关闭配置窗口后仅刷新绘制函数，真实前台 Blender 的 HTTP 和 SSE 均完整显示“复制”，地址同行，两服务仍在运行，场景保持第 33 帧；没有整包重载或更改 Token。
- 生成创建回执允许只有任务 ID；查询回执不再允许空对象、空状态列表、非字符串或空白状态伪装成“生成中”。无效响应走既有有限重试，耗尽后提示“远端状态未知”，不重提付费任务。
- 新增 6 组无效响应反例均在修复前失败，修复后与任务注册表、生成状态、布局回归合计 24 项通过。这是源码线程测试证据，未发布、未同步到正式运行实例，不代表真实外部供应商验收通过。
- 当前源码重新打包至 `/tmp/partme-poll-validation.wYAqlQ/dist`，在独立 `BLENDER_USER_CONFIG` 的 Blender 5.2.1 中运行 `native_provider_polling_smoke.py`，退出 0：正常/取消场景共 2 次后台查询，无效状态连续 2 次后停止，主线程可操作，付费请求 0。提交函数为 fixture，此证据只覆盖真实 Add-on 中的轮询与取消，不覆盖官方提交后台化或真实模型生成。

### 正式安装与源码差异审计

最新候选位于 `/tmp/partme-mcp-final-candidate.R6oBoO`。候选 Add-on 已覆盖到 Blender 5.2 正式 Add-on 目录，覆盖后逐文件核对无差异；覆盖前安装保存在 `/tmp/partme-blender-installed-pre-hyper3d-20260920`。这只证明磁盘安装内容一致。

当前 Blender 5.2.1 进程仍持有覆盖前已加载模块，且窗口标题显示场景尚未保存。为避免丢失用户工作，本轮没有自动关闭或重启 Blender。因此后台轮询、本地生成、受控导入、Hyper3D 双认证等候选能力仍需在用户保存后重启并复验，不能归属当前内存实例。

候选 `dist/` 中三个 ZIP、一个 tar.gz 均通过归档完整性检查；`SHA256SUMS.txt` 对 SBOM、manifest 和四个发布资产逐项验证通过。该证据只证明本地候选完整，不等于 GitHub Release 已发布或插件 runtime lock 已更新。

### 当前工作树回归汇总

- Hyper3D 已实现互斥的客户端 OAuth 与 API Key 两条路径：OAuth 固定复用 `hyper3d` + `https://api.hyper3d.com/api/mcp`，只通过 Codex/Claude Code CLI 检测登录状态，不读取或保存 Token；API Key 继续使用 Blender 本机偏好并调用官方 `api/v2`。顶部“刷新状态”会重新读取客户端登录事实，外部完成授权后不再依赖 Blender 内旧枚举。
- 当前 Codex 全局配置保留了正确的 `hyper3d` Streamable HTTP 条目。用户已在 Hyper3D 浏览器页面完成授权，`codex mcp login hyper3d` 返回成功，当前 shell CLI `0.147.0` 与桌面内置 CLI `0.155.0-alpha.9.2` 均报告 `auth_status=o_auth`；OAuth Token 仍只由客户端保管，未被 Blender 或验收脚本读取。
- 授权成功不等于连接成功。两版 Codex 的真实 MCP 启动均在 `notifications/initialized` 阶段失败：Hyper3D 对通知返回合法的 HTTP 202 空响应且不带 `Content-Type`，当前 Codex/rmcp 将其拒绝为 `Unexpected content type: Some("missing-content-type; body: ")`。因此当前验收结论为“OAuth 已授权、Codex 连接失败”，不能把 Hyper3D 计入供应商可用，也不能宣称工具已由 Codex 暴露。该症状与上游公开问题 `openai/codex#26955`、`openai/codex#14793` 一致。
- 直接协议探测确认端点以 MCP `2025-06-18` 初始化并报告 `serverInfo.name=hyper3d-rodin`、`version=1.0.0`。匿名 `tools/list` 当前返回 7 项：`rodin_create_uploads`、`rodin_import_images`、`rodin_generate`、`rodin_generate_bang`、`rodin_get_status`、`rodin_wait`、`rodin_get_result`；这只证明目录可发现，不表示已授权执行。
- 对只读 `rodin_get_status` 的无凭证调用返回 HTTP 401，`WWW-Authenticate` 指向标准 protected-resource metadata。该元数据声明资源为 `https://api.hyper3d.com/api/mcp`、授权服务器为 `https://api.hyper3d.com/api/grant/oauth`、作用域为 `rodin:generate` / `rodin:read`；授权服务器元数据声明 Authorization Code、Refresh Token、Device Code 与 PKCE S256。未调用生成、未消耗积分。
- 临时官方 SDK 环境完整回归为 179 项全部通过、0 跳过。隔离 Blender 5.2.1 从新候选 ZIP 启用后验证 OAuth/API Key 两模式、RNA 注册和状态切换，退出 0，外部网络与付费调用均为 0。
- 正式发布构建不再产出独立 `partme-community-addon-2.0.0.zip`，manifest、校验和与分发测试同步收紧；社区 MIT 后端仅作为 PartMe 主 Add-on 内部实现并保留第三方声明，不再形成第二个可安装插件。
- Runtime：使用已安装官方 SDK 的 0.5.1 venv 解释器并显式 `PYTHONPATH=src`，`unittest discover -s tests -p 'test_*.py' -q` 共 179 项全部通过、0 跳过、退出 0。
- 首次系统 Python 测试暴露旧界面契约仍要求已删除长提示与静态播放文案；根据用户确认的单行提示和动态播放/暂停设计更新断言，没有恢复旧布局。系统 Python 缺少 SDK 导致的 4 项跳过，已由上述 venv 全量运行补齐。
- Plugin：当前工作树同类 unittest discover 共 481 项，480 通过、1 跳过、退出 0。唯一跳过为 Windows named pipes（当前 macOS 不具备该平台条件）；测试中的坏清单、SHA 不匹配输出来自拒绝反例，不是最终失败。
- 两仓回归通过不替代真实付费供应商、Windows、三宿主、最终安装包一致性和 UI 像素级验收。发布及锁定包同步仍未完成。

### 插件层运行时绑定检查

- 修复插件兼容生成状态：Done + Processing 不再提前完成，INCOMPLETE 不再因包含 COMPLETE 被误判；全部子结果成功才显示完成，失败优先，取消显示终态，NaN/Inf 进度不显示。6 项新增测试中 4 项在修复前失败，修复后与插件集成测试合计 35 项通过。此为兼容层 fixture/单元证据，非真实供应商生成验收；仍待版本发布。

- 确认插件已有 `test_real_plugin_adapter_paginates_the_combined_catalog_once`，实际实例化锁定包 McpAdapter 的插件子类，按每页 7 项检查 5 个扩展工具仅出现一次；并非只测试基础适配器。
- 新发现并修复 `blender-design-plugin/scripts/partme_runtime.py` 只核对版本、会接受外部同版本缓存模块的问题。现在校验已加载包及子模块均来自锁定 ZIP，来源冲突时明确拒绝并要求重新从插件入口启动，不静默清空运行中模块。
- 新增两项来源冲突测试先失败后通过；插件运行时集成和社区兼容测试共 29 项通过。插件版本升级、上游新版本发布后更新 runtime.lock、市场同步仍待统一收尾；本轮没有修改 vendor ZIP 或发布。

### 事务、审批和回滚的公开 MCP 复验

- 加固 `generic_mcp_client_handshake.py`：从传入候选包加载服务实现，明确断言结果；总时限 90 秒，异常先终止子进程再读取日志，不再以打印报告或进程自然结束作为通过。
- 在隔离 Blender 5.2.1 中针对 `rna-fixed-addon` 实测：176 工具、4 页；事务创建 HandshakeProbe 并提交成功；未批准删除返回 AUTHORIZATION_REQUIRED 且对象仍存在；测试宿主批准指定 requestId 后重试删除成功；回滚从真实 .blend 检查点恢复对象；待审批数量 0，客户端和 Blender 均退出 0。
- 证据目录 `/tmp/pbm-hs-wpvpwwh0`。仅操作测试进程内新建对象，未修改用户当前场景；审批由测试宿主模拟，不代表人工 UI 审批交互已全部验收。

### 最新源码候选包三传输协议复验

- 鉴权新增真实 HTTP 请求反例：HTTP/SSE 缺少 Token、错误 Token 四项均返回 401；合法 Token 的协议及目录复验仍通过，退出 0。
- RNA 枚举集合警告已在 PartMe 执行器修复：读取 `default_flag` 并转为排序数组，不再读取单选 `default`；新增防误读回归测试通过。重新打包到 `rna-fixed-dist` 后，7 项基础查询在真实 Blender 再次通过且没有原来的枚举警告。该修复尚未同步到用户正在运行的旧执行器。

- 后续增强脚本逐页调用官方 SDK `list_tools`：三个传输均为 176 个工具、4 页，无重复工具名和循环游标；每个输入 schema 为 object，所有公开属性均具有类型约束。修复文件路径与相机曲线路径的同名 schema 冲突，并补齐 `asset.fetch_generated.params`、预算、渲染、绑定、版本和运行时字段类型后，三传输名称/schema 排序摘要一致：`54d104c43892994fab199c78f4d3e01ea39f7e73034e42f8d8a6797be467a2df`。实际运行退出 0。
- `capability.describe` / `capability.list` 现可从公开 MCP JSON 参数安全转换 profile/runtime，不再要求调用方传入 Python 内部对象；新增 `test_capability_api.py` 覆盖有效转换与无效输入拒绝。
- 此为运行时工具目录一致性证据，不代表插件扩展工具目录或 176 项全部执行成功。
- 同一候选包的 `native_base_query_smoke.py` 真实 Blender 复验退出 0：ping、Add-on 信息、场景信息、世界状态、对象信息、节点类型及 bpy API 查询共 7 项通过，场景对象和节点组未改变。运行中出现 bpy 枚举默认值警告，未导致断言失败，仍需追踪警告来源。

- 候选包：`/tmp/partme-current-transport.gBIpmh/dist/partme-blender-mcp-addon-0.5.1.zip`，由当前源码重新打包；未发布、未替换 Codex 插件缓存。
- 使用独立且实际存在的 `BLENDER_USER_CONFIG` 和 `PARTME_BLENDER_RUNTIME_DIR`，在 Blender 5.2.1 后台运行；无真实模型调用，不更改当前用户场景和服务监听。
- `tests/runtime/remote_transport_smoke.py` 新增官方 SDK stdio 客户端真实握手及 `blender_connection_status` 调用；此前仅测 stdio ready 不足以证明协议可用。
- 最新实测 stdio、Streamable HTTP、SSE 均返回 `server=partme-blender-mcp, connected=true, isError=false`，脚本退出 0。
- HTTP/SSE 同时在线，客户端数量各 1；单独关闭 HTTP 后 SSE 仍运行，最终均关闭且 Add-on 成功停用。
- 此证据覆盖本机官方 SDK 协议握手、连接状态工具、监听生命周期，不覆盖所有工具、跨机 TLS、Windows 或真实 Codex/ZCode/Kimi 宿主验收。

### 制作页定稿布局纠偏

- 最新实现改为四个 box 外框，每张卡片内部为上图标、下文字的无边框操作区，取消横排过渡方案和八块可见按钮。两个区域共享同一 view 参数；真实前台点击正面文字区、顶面图标区均生效。卡片外缘留白不是完整点击目标，原生 box 底色也不等同定稿灰色按钮，仍不能宣称像素级还原。
- 真实播放复验：按钮切换为蓝色暂停态和 PAUSE 图标，侧栏帧数随播放更新（0.1 秒刷新）；停止后恢复播放态。测试后恢复顶面、第 33 帧。10 项布局及重绘测试通过。

- 用户指出上下双按钮产生八块后，已撤销双 operator 拼接：现在每个视角只创建一个含图标和文字的 operator，实际 Blender 显示四块且无上下分割线。当前为原生横排图文，不冒充定稿要求的纵向单块图文；该视觉差距仍待解决。
- 新增播放状态变化重绘器，9 项布局/状态测试通过；真实 Blender 后台确认启用时注册、停用时清理 timer。当前前台已热加载，播放期间实时重绘仍需实屏复验。

- 后续前台真实点击验证：正面文字按钮、侧面图标按钮、相机图标按钮、顶面文字按钮均改变对应视角；播放使时间轴前进，第二次点击停止。侧栏帧输入成功将时间轴恢复第 33 帧，视角恢复顶面。
- 发现播放中侧栏图标仍为静态 PLAY，帧数显示滞后。源码与安装文件已改为按真实播放状态显示播放/暂停图标及文案；该新状态显示尚待热加载和重绘联动验收，不能视作已通过。

- 删除窄栏下会话 ID 与播放控件的强制拆行；会话 ID、复制同一行，播放与帧同一行。
- 暂停、撤销和审批放入制作卡片；无进度时不显示重复的英文 Ready。
- 四个视角恢复等宽图标上、文字下的组合控件；两处点击均绑定原有 change_view 操作。
- 7 项布局回归通过（新增目标测试先失败后通过），安装目录同步并在当前 Blender 热更新，实屏确认上述结构生效。
- 仍使用原生上下两个按钮构成快捷控件，不是设计稿单块按钮的像素级还原；尚未宣称全界面视觉验收完成。未改动凭证或 MCP 协议。

### 素材页操作与紧凑文案修复（最新增量）

- 删除重复“素材库”标题，提示改为单行“自动搜索，下载仅写授权目录”；当前 Blender 窄侧栏实屏确认无换行。
- 已安装 Add-on 的 Poly Haven、Sketchfab 状态与配置改为 PartMe 原生绑定，不再要求独立社区服务；同步原生查询命令。
- 当前运行 Blender 实测 Poly Haven 关闭后可用数由 2/6 降为 1/6，重新启用恢复 2/6；Sketchfab 齿轮打开配置，勾选打开“保存并启用”，取消未写入密钥。
- 已安装执行器在隔离 BLENDER_USER_CONFIG 的 Blender 5.2.1 中真实请求 Poly Haven 模型分类，返回 45 项、退出码 0。没有模型生成付费调用。
- 布局、供应商偏好和启用流程共 13 项 unittest 通过。热更新偏好类时在内存保存并断言恢复已有偏好，不输出凭证。
- 此为本地安装和当前进程的针对性修复，不代表完整源码发布、Codex 缓存更新或 Sketchfab 真实密钥下载验收已完成。

### 用户确认的替代边界（本轮优先级最高）

只安装并启用 PartMe Add-on，替代独立社区插件；不能以同时安装 `blender_mcp_community` 作为供应商功能可用的前提。此前双插件测试仅为旧架构回归，不能作为独立替代验收。

- 已将当前源码候选包装入 Blender 5.2 正式 Add-on 目录并启用、保存偏好；stdio 就绪，当前 Codex 实际连接成功。
- 本轮误装的独立社区 Add-on 已停用、移出 Add-on 目录，保留可恢复副本于 `/tmp/partme-install-candidate-20260920/removed-community-addon`；PartMe 保持启用和连接。
- 单插件实测暴露依赖缺口：Poly Haven 显示不可用。源码仍通过社区偏好保存 Sketchfab / Rodin / 混元配置，并通过社区状态与命令桥执行能力，因此尚未实现完整替代。
- 下一阶段必须移除独立社区安装前置条件，将供应商配置、执行与状态归入 PartMe 所有；保留原生 Poly Pizza 主路径、风险分级、授权目录和事务导入。只隐藏社区面板或改状态文案不满足验收。

基线：侧栏设计文档「社区式紧凑行」修订与供应商整合计划。当前是未发布源码修改，版本标识仍为 0.5.1；临时构建不能覆盖同名正式发布资产。插件回执 schema 的兼容修复也尚未发布，完成前需按插件 AGENTS.md bump 并同步市场。

## 界面

- 素材、模型采用左侧小勾选框、图标名称、右侧状态点及小齿轮，异常与任务详情按需展开。
- HTTP/SSE 左侧启停控件与真实运行状态分离，保留 Token 配置和安全限制。
- 已恢复前台六供应商正式目录：local_library、polyhaven、sketchfab、polypizza、hyper3d、hunyuan3d。
- 仅移除此前演示脚本写入的 hunyuan3d / visible-acceptance 任务；没有终止第三方任务，没有移除其他用户任务。
- 前期 UI 曾通过临时 Add-on 加载；本轮已将最终候选覆盖到正式 Add-on 目录并逐文件核对，但当前进程尚未重载。正式版本发布、runtime lock 更新及保存后重启验收仍待完成。

## 本轮实际修复

### 模型页无法配置/启用（后续修复）

后续入口迁移：插件源码中的 `blender_community_call` 对 Rodin/混元状态、创建、查询已改走 `provider.status` / `provider.external_action` / `provider.query`，无社区 socket 回退。创建与审批合并为一次受控执行，拒绝后不更新任务或继续调用供应商。只读查询固定 risk=read，执行器拒绝生成命令。新增两个只读运行时入口后，公开命令数为 171。此项是源码和候选包验证，不表示已运行的宿主缓存自动升级；旧工具的资产路径、自动安装流程与发布版本锁仍需迁移。

- Rodin、混元凭证及平台选项迁入 PartMe 偏好；不再写社区 Add-on 偏好或依赖其开关属性。未配置显示黄色“需要配置凭证”；配置并勾选后允许路由，但不声称已验证远端密钥。
- PartMe 包内加入进程内 `provider_engine`，按 MIT 声明复用 vendored 客户端代码，不调用社区 register、不注册社区面板、不创建 9876 监听器。
- `provider.external_action` 支持 `params` 并执行白名单内的 Rodin/混元创建与查询，校验 provider/action/risk 对应关系；保留审批、预算门禁。公开通用工具 `blender_provider_external_action`；旧的无 params 许可回执兼容保留。公开命令数变为 169。
- 新通用入口不等于旧 `blender_community_call` 已迁移：旧插件适配器路由、结果下载导入、完整任务生命周期及真实付费端到端验收仍待收尾；现有已运行的 MCP 服务目录需要重新加载才会出现新工具。
- 118 项测试通过；`native_model_enable_smoke.py` 在仅启用 PartMe 的真实 Blender 中验证两供应商缺凭证、启用、停用，以及替身执行分发和伪造低风险拒绝。HTTP 被替身替代，付费网络调用为零。
- 当前前台已加载新偏好及模型配置操作；实际点击 Rodin 齿轮成功弹出配置表单。未填写用户密钥，未提交生成任务。候选版本尚未公开发布。

### 关闭监听器后日志撑满页面（后续修复）

- `remote.poll` 不再把进程日志末尾 512 字符写入用户提示；正常关闭提示为空，异常退出仅返回短摘要。
- 接入页仅展示异常/配置摘要，日志文件入口置于默认折叠的“诊断详情”，HTTP/SSE 独立保存展开状态。
- 两项新增回归先失败后通过，远程监听测试共 10 项通过；安装目录真实 Blender HTTP/SSE 客户端握手和独立启停通过。
- 当前前台 Blender 已热更新，保留原有 HTTP 进程；实际点击 SSE 开启后关闭，确认“已关闭”且不再铺开 INFO 日志。源码和本地安装均已更新，尚未发布新版本。

1. 失效 socket 转为 BLENDER_NOT_CONNECTED，避免旧会话描述文件使 doctor 崩溃。
2. 远程监听绑定启动它的 Blender 会话；不同会话使用独立日志和状态文件，避免多窗口自动发现歧义。
3. 后台任务从自身目录加载 frame worker，不再误用 Blender 预加载的旧 Add-on；实际帧回执 producer 已确认为 partme-blender-mcp / 0.5.1。
4. 插件帧序列及视频回执 schema 同时接受旧 codex-blender 与当前 partme-blender-mcp，仍拒绝未知 producer。

## 验证证据

| 范围 | 本轮结果 | 边界 |
|---|---|---|
| runtime 单元/分发/SDK 测试 | 114 tests 通过，无跳过 | Python 3.13，非真实外部生成 |
| plugin 全套回归（schema 修复前） | 467 tests，1 skipped | 平台限定跳过，不证明新 schema |
| plugin schema 修复后定向回归 | 13 tests 通过 | 包含新旧 producer 及未知 producer 拒绝 |
| 正式六供应商目录与 Poly Haven 启停 | 真实 Blender 通过 | 未进行资产下载 |
| Add-on 审批、预算、事务回滚、接管重检 | 真实 Blender 通过 | 隔离测试工程 |
| 官方 SDK stdio | 当前候选握手、4 页 / 176 个工具、读写、审批及回滚通过 | 通用协议客户端，不是三个宿主的重新验收 |
| 官方 SDK HTTP/SSE | 当前候选各 1 客户端，4 页 / 176 个工具且 schema 摘要与 stdio 一致，独立启停通过 | loopback + Bearer Token，不是公网 TLS/内网穿透验收 |
| 雕刻笔刷 | 顶点最大变化 0.1777203 | 独立前台进程 |
| 跟踪解算 | 重投影误差 0.6174927 px，通过 | 合成已知轨迹片段，不是用户真实素材 |
| 视角、聚焦、播放、审阅窗口 | 独立前台进程通过 | 不修改用户当前工程 |
| 帧序列修复、EXR、视频合成 | 当前源码重测通过 | 故障注入第 2 帧损坏及第 3 帧缺失 |

逐项调用记录见 `ui-function-coverage-2026-09-20.json`：27 个独立场景用例最终均通过，171 项内部注册命令中 164 项在通过用例中有成功 dispatch 记录。历史失败也保留，不能把第一次失败删除后冒充一次通过。

这个数字只表示命令调用覆盖，不是所有参数、全部平台或生产质量的覆盖率。provider 状态机测试没有调用付费供应商；provider.external_action 的许可回执不是第三方请求成功证明。内部注册目录与 MCP 公开工具目录口径不同。

复现入口：`tests/runtime/run_existing_acceptance.py` 强制复用当前 runtime 源码而非插件内历史 harness；输入具体插件用例路径及全新输出目录。完整本机运行输出位于 `/tmp/partme-ui-completion-build/evidence/`，临时目录不保证长期保存。

## 未完成门禁

- asset.fetch_url、asset.fetch_generated、asset.polypizza_search、asset.polypizza_download 的真实外部端到端验证；需要供应商授权、适用密钥和合法资产。
- 社区 Rodin / 混元真实提交、查询、下载、事务导入、取消语义及费用验证；需用户明确预算，禁止使用模拟 68% 充当通过。
- rig.rigify_install、rig.rigify_generate：需确认扩展安装范围，不能为测试静默下载安装。
- advanced.execute_python：受限专家能力，保持公开 MCP 不暴露，不为提高成功覆盖数降低门禁。
- 新 UI 宽窄尺寸及错误/审批状态最终复核，正式安装后重启复核。
- 新版本构建发布、插件 runtime.lock.json 更新、市场同步与实际安装缓存验证。
- Windows 与 Codex / ZCode / Kimi 当前构建验收；本报告不沿用旧版本通过记录。
# 补充：模型勾选无响应修复

- 将缺少凭证时的禁用勾选改为配置引导；配置完整后“保存并启用”，齿轮只保存配置。
- Blender 5.2.1 当前运行窗口：实际点击 Rodin 和腾讯混元左侧勾选，均打开对应配置，显示“保存并启用”；取消后均保持未启用。
- 已同步本机已安装的 panel.py，并局部热更新两项操作与绘制函数；未重启监听器，未改动 Token 或用户场景。
- 保存自动启用、配置不完整不启用、齿轮不隐式启用由隔离单元测试覆盖；没有真实凭证，因此不宣称远端生成验证通过。
- 本次为本机修复，尚未发布新版本。
# 补充：独立素材查询迁移

- Poly Haven / Sketchfab 的状态与启停改由 PartMe 管理；Sketchfab 密钥不再读取社区 Add-on 偏好。
- Poly Haven 分类/搜索与 Sketchfab 搜索通过 PartMe `provider.query` 执行；兼容旧工具名但这些查询不回退 9876。
- 独立打包候选在 Blender 5.2.1 `--background --factory-startup --python-exit-code 1` 下真实取得 Poly Haven 45 个模型分类，社区 Add-on 未启用，付费调用为 0。
- 当前运行时 123 项单元测试通过，插件社区兼容与原生路由测试 18 项通过。
- 边界：Sketchfab 真实鉴权/搜索、素材下载/预览/事务导入及旧汇总状态仍需迁移和验收；此次素材修改仅在源代码及隔离候选验证，尚未更新当前 GUI 安装或公开发布。
# 补充：受控供应商结果暂存

- `asset.fetch_generated` 增加供应商引用 `params` 路径；与 `url`/`filename` 互斥。Sketchfab/Rodin 签名 URL 在 PartMe 内部解析并消费，不再经社区 9876 或插件返回。
- 补齐会话层 `asset.fetch_generated` 强制审批。回归测试先证实旧实现未审批会执行，再验证拒绝时不 dispatch、批准后才执行。
- 未配置授权素材根时不调用供应商解析器；暂存仍使用原有下载上限与 ZIP 路径校验，不自动导入场景。
- 供应商解析/下载使用测试替身，尚未取得真实凭证验证 Sketchfab/Rodin 下载。源代码修改尚未安装至 GUI 或发布。
# 补充：MCP 供应商状态与预览入口

- 兼容工具 `blender_community_status` 改为查询 PartMe `provider.status`，不再探测社区端口，返回与 UI 相同的供应商快照。
- Sketchfab 预览走 PartMe `provider.query`，仅内存读取；缩略图域名限 Sketchfab、拒绝重定向、最大 5MB、仅 PNG/JPEG，缩略图请求不携带 API Key。
- 插件将预览作为 MCP image content 返回，元数据不重复嵌入 base64。
- 域名、体积、格式、凭证隔离以及 MCP image content 均有替身测试；未使用真实 Sketchfab 凭证，尚无线上预览验收。本轮仍是源码修改，未更新 GUI 安装或公开发布。
# 补充：独立安装包供应商目录

- Add-on 自带 `providers.json`，包含 Poly Haven、Sketchfab、Rodin、混元四项描述，结合 Harness 原生本地库与 Poly Pizza 共六项；无需插件安装阶段另行补写。
- 目录描述不包含社区开关属性或社区偏好模块。插件仍可贡献完整替代目录，加载时沿用统一校验与状态协议。
- 打包重复条目检查移至所有资源添加之后。
- 全新隔离 Blender 5.2.1 启用仅从 ZIP 解压的 PartMe 包，确认六项注册，并成功查询 Poly Haven 45 个模型分类；未复制插件配置，未启用社区 Add-on。
- 13 项包结构测试通过；此为未发布候选，当前 GUI 安装没有改动。
# 补充：基础查询兼容入口迁移

- `ping`、`get_addon_info`、`get_scene_info`、`get_world_state_snapshot`、`get_object_info`、`describe_node_type`、`bpy_api_lookup` 通过 PartMe `provider.query` 执行，不再连接社区 9876。
- 插件信息明确返回 PartMe 名称、版本及当前白名单，不再宣称提供社区 `execute_code`。
- 独立打包候选在 Blender 5.2.1 完成七项真实调用，全部成功；调用前后对象和节点组集合保持一致。
- 插件相关测试 21 项通过。旧截图/导出兼容入口仍需接入授权路径；本轮源代码尚未更新当前 GUI 或发布。
# 补充：截图与导出兼容入口

- 最后两个旧入口已路由至 PartMe：截图通过只读 `provider.query`，导出通过强制审批的 `provider.external_action`；插件删除了剩余社区 socket 回退。
- 新 `compat_io` 限定授权输出根、拒绝覆盖已有文件、校验扩展名和参数。导出复用原生 Exporter 回执，并恢复选择、活动对象和模式。
- 真实 Blender 5.2.1 已验证 GLB/FBX 先拒绝后批准、有效文件生成、越界拒绝、只读伪装拒绝和选择恢复。
- 截图仅完成路径守卫测试，实际前台截图成图待验证；本轮尚未更新当前 GUI 安装或发布。
# 补充：取消终态与前台验证阻塞

- 本轮前台工具明确返回 Mac 已锁定，未尝试绕过锁屏；实际截图验证仍待用户解锁。
- 修复取消任务被迟到的生成/完成/start 回执复活的问题，取消后同一任务 ID 的更新保留原终态。
- 原生 Rodin/混元查询和供应商下载解析前检查本地取消记录；已取消则在调用后端前返回 `PROVIDER_TASK_CANCELLED`。
- 插件补充识别 `task_uuid`。这些行为只停止本地后续处理，不声称已经取消供应商远端计费任务。
- 33 项供应商相关测试通过（含取消前置拦截）；当前 GUI 尚未安装此补丁。
# 事故记录：测试写入正式 Blender 偏好（已从原窗口恢复）

- 原生模型任务联动测试启动时仅设置 `BLENDER_USER_RESOURCES`，实际保存日志却指向正式 `5.2/config/userpref.blend`；测试错误覆盖了磁盘偏好。不得将此次运行报告为通过。
- 当前前台 Blender 进程 8822 仍在运行，需用户解锁后优先将当前窗口内存中的真实偏好保存回磁盘；不要退出该窗口。正式配置目录没有发现可用备份。
- 已停止会写偏好的测试，将本次写入文件保留为 `/tmp/partme-enable-flow.mMfHKG/userpref.test-write.backup.blend` 便于核查；该文件不是原始偏好的恢复副本。
- 测试新增前置断言：必须显式设置 `BLENDER_USER_CONFIG`，且 `bpy.utils.user_resource('CONFIG')` 必须准确等于隔离目录，否则在启用 Add-on 之前终止。
- 原生任务适配本身的 135 项单元测试及插件 21 项相关测试通过；真实模型任务联动验证尚未通过，偏好恢复尚未完成。

## 后续恢复与重新验证

- 上述段落记录事故发生时的状态。解锁后已在原 Blender 进程 8822 中核实测试凭证不存在、原 Token 仍配置，再从该窗口保存偏好；保存结果为 `FINISHED`。这是运行中偏好的恢复，不声称与事故前磁盘文件逐字节一致。
- 恢复回执：`/tmp/partme-enable-flow.mMfHKG/preferences-restored.json`；恢复后备份：`/tmp/partme-enable-flow.mMfHKG/userpref.restored.backup.blend`，均为临时本机证据，非发布产物。
- 重新执行四项模型启用联动单元测试，全部通过。
- 使用实际存在的独立 `BLENDER_USER_CONFIG=/tmp/partme-model-config.UeK8Qw`，在 Blender 5.2.1 执行 `native_model_enable_smoke.py` 成功：两个模型启用/关闭、任务状态联动、风险降级拒绝均通过；供应商 HTTP 使用替身，付费请求为零。
- 实际保存日志全部指向该临时配置目录；测试前后正式 `userpref.blend` 的 SHA-256 完全一致。
- 当前仍没有真实模型凭证与付费预算，不宣称远端生成、下载及完整产品验收通过。

## 补充：官方混元生成结果暂存

- 原生 `resolve_hunyuan_asset(job_id)` 读取官方任务查询结果，仅接受 `DONE` 且没有错误的结果；优先 GLB，其次 FBX、包含 OBJ 的 ZIP。拒绝 HTTP、非腾讯 COS 主机、非标准 HTTPS 端口、URL 凭证以及格式不匹配。
- 查询结构依据[腾讯云官方查询接口](https://cloud.tencent.com/document/api/1804/123448)的 `Response.Status` 和 `ResultFile3Ds`，不沿用社区直接导入逻辑。
- 插件 `blender_provider_stage_asset` 接受 `hunyuan3d` + `params.job_id`，完整传递授权、事务及场景版本到原生 `asset.fetch_generated`；解析 URL 只在下载内部消费，导入仍是独立事务步骤。
- 先验证新增测试因缺失解析方法/插件拒绝供应商失败，再实现。预览/解析测试 8 项、资产守卫测试 9 项、插件兼容路由测试 22 项通过。
- 本轮为源码与替身测试证据，未执行真实混元下载、未更新当前 Blender 安装、未发布。官方与本地服务模式明确区分，本地模式尚不支持该任务引用路径。
- 主线程网络阻塞、原生自动轮询调度及完整取消/导入链仍未完成，已列为新的明确门禁。

## 补充：原生后台自动轮询（源码阶段）

- 新增 `ProviderPoller`，Rodin 官网/fal 与混元官方提交成功后启动只读后台查询；每任务去重，最多 8 个工作线程，查询间隔 5 秒，连续 3 次异常或 2 小时到期停止。
- 查询回调在主线程捕获普通配置值，后台不访问 `bpy`；HTTP 设置连接/读取超时并拒绝重定向，异常原文不进入任务状态。Blender 主线程定时器在任务快照变化时刷新侧栏。
- 已提交任务即使无法启动轮询，也返回“已提交、自动查询未启动”的任务状态，避免误报提交失败诱发重复计费。
- 取消/卸载后丢弃在途查询结果，不声明远端计费任务已取消。生成提交与下载仍有同步实现，未消除所有主线程阻塞；本地混元自动查询仍待实现。
- 45 项供应商单元测试通过，包含慢查询与取消并发、去重、连续异常、总时限、卸载后丢弃结果，以及配置捕获后移除 Blender 上下文仍可查询。
- 尚未在前台 Blender 和真实供应商上验证此后台轮询补丁，未安装或发布；不据此关闭整体生成验收门禁。

## 补充：打包后 Blender 后台轮询验收

- 从源码重新构建临时候选 `/tmp/partme-poll-build.Vgv2aK/partme-blender-mcp-addon-0.5.1.zip`，解压至独立安装目录，以真实 Blender 5.2.1 执行 `tests/runtime/native_provider_polling_smoke.py`。
- 两次提交回执实际启动后台 HTTP 替身查询；请求阻塞期间主线程成功改变帧号和请求本地取消。晚到完成响应没有复活取消任务，正常任务自动完成，UI 刷新定时器注册与卸载均通过。
- 输出 `NATIVE_PROVIDER_POLLING={passed:true,backgroundQueries:2,mainThreadResponsive:true,paidNetworkCalls:0}`，进程退出码 0。显式隔离配置，正式偏好文件 SHA-256 前后相同。
- 这是后台模式中的实际 Blender 运行证据，不等于前台点击、真实网络/付费供应商或正式安装验收。
- 随后补充乱序响应回归：旧 RUN 响应可将已完成任务复活，测试先失败；注册表锁内增加生成完成状态保护后，46 项供应商测试通过。该额外保护尚未进入上述临时候选包。

## 补充：本地混元旧导入路径隔离

- 源码审计发现上游 `create_hunyuan_job_local_site` 将 `/generate` 响应写入系统临时目录，并通过 `bpy.app.timers` 直接执行 glTF 导入；这绕过 PartMe 授权素材目录与事务约束。
- 原生执行器现在在调用旧 handler 前拒绝本地混元提交/查询，返回 `PROVIDER_UNAVAILABLE`；注册表同步显示“本地受控生成尚未接通”，不再计入可用数。官方混元路径保持不变。
- 两项新增测试先重现旧 handler 可达及状态误报 ready，再通过补丁；48 项供应商测试通过。
- 此为临时安全隔离，不是本地混元功能完成。仍须实现无自动导入的后台 `/generate` 客户端、授权目录暂存、可取消任务状态与独立事务导入，再恢复本地模式可用状态。
- 本补丁尚未安装或发布；正式可用性与发布验收门禁仍未关闭。

## 补充：本地混元受控后台路径替代临时隔离

- 新增 `LocalGeneration`：后台调用配置的本地 `/generate`，立即返回 `local_` 任务 ID；不调用旧社区自动导入 handler。配置复制后线程不使用 `bpy`。
- 要求授权素材根，图片输入只接受授权文件；二进制响应限制 500MB，检查 GLB 文件头/版本/长度后在独立目录发布。取消或异常时不返回可导入结果，未完成文件清理；不显示异常原文。
- 原生任务查询和 `asset.fetch_generated` 已支持本地任务，取得路径时再次核对当前授权根。注册表恢复本地模式配置状态，但仍明确未验证远端服务。导入保持独立事务，不自动执行。
- 本地服务 4 项单元测试通过：授权前拒绝、成功暂存、在途取消、错误/超大响应丢弃。旧 handler 不可达回归仍保留。
- 打包候选 `/tmp/partme-poll-build.Vgv2aK/local-candidate/partme-blender-mcp-addon-0.5.1.zip` 在 Blender 5.2.1 执行 `native_local_generation_smoke.py`：真实本机 HTTP 往返 1 次，1936 字节 GLB 完整暂存；原生提交/查询/取回成功，场景对象集合不变，正式偏好 SHA-256 不变。
- 此次使用本机测试 HTTP 服务返回已知模型，不是实际混元推理服务验收；未验证模型质量、前台按钮点击、进程重启恢复。未更新正式安装或发布。

## 补充：本地模型完整事务导入链验证

- 扩展同一 `native_local_generation_smoke.py`，使用真实 `HarnessSession`、`TransactionManager` 和 `BlenderCheckpointStore`，而非模拟场景对象或事务结果。
- 已暂存模型在无授权素材根时返回 `ASSET_NOT_AUTHORIZED`；未开始事务时返回 `TRANSACTION_NOT_FOUND`；错误场景版本返回 `STALE_SCENE_REVISION`。三种拒绝均没有增加场景对象。
- 正确开始事务后实际导入 1936 字节 GLB，新增 1 个对象；`changedObjects` 与实际新增对象集合一致，对象回执数量一致，`sceneRevision` 为 1。提交成功，包含 `snapshotId`，事务日志状态为 committed。
- 使用上述临时候选包在真实 Blender 5.2.1 运行成功，进程退出码 0；正式偏好 SHA-256 未改变，外部付费请求 0。
- 本地 HTTP fixture → 后台暂存 → 原生查询 → 授权路径 → 事务导入 → 快照回执已取得运行证据；真实推理服务、前台交互和正式安装/发布仍未验收。

## 补充：官方提交请求与参考图边界

- Rodin 官网/fal 提交与混元官方提交/手动查询改由 PartMe 覆盖实现，设置连接 5 秒、读取 30 秒超时，拒绝重定向，不输出供应商原始异常或签名内容。此为连接/读取超时，不是整体任务时限。
- 混元本地参考图只能来自当前授权素材根，PNG/JPEG 最大 20MB；远程引用只接受不含 URL 用户凭证的 HTTPS。运行时将授权根直接传给执行器，不信任客户端额外声明的根目录。
- 混元提交复制 profile body，不在共享模板中残留前一次 Prompt/Image。Rodin 官网图片输入增加数量、格式与体积检查。
- 三项新增边界测试先因 PartMe 覆盖方法缺失失败，实现后供应商相关 51 项测试通过。
- 官方提交仍是主线程同步调用，不能将这些超时配置当作 UI 非阻塞证明。未发送真实付费请求，尚未更新正式安装或发布。

## 补充：Hyper3D OAuth 授权与 Codex 连接边界

- 用户已完成浏览器授权；当前 `hyper3d` 配置仍为固定 Streamable HTTP 地址 `https://api.hyper3d.com/api/mcp`，Codex 报告 `auth_status=o_auth`，没有覆盖其他 MCP 设置。
- 状态探针不再把 OAuth 授权事实直接映射为 `ready`：授权后、真实 MCP 握手未通过时返回 `unavailable / OAuth 已授权 · 客户端连接待验证`，从供应商可用数和自动路由中排除。对应测试先失败后修复，完整 179 项回归通过。
- 当前 Codex 真实连接仍因 initialized 通知的 HTTP 202 空响应缺少 `Content-Type` 而失败。直接匿名协议探测列出的 7 个工具只是服务目录证据，不是 Codex 已连接证据；未调用任何生成工具，未消耗积分。
- 新候选位于 `/tmp/partme-hyper3d-oauth.Bw3638/dist`，四个发布归档、manifest 与 SBOM 的 `SHA256SUMS.txt` 全部验证通过；Add-on ZIP 内已核对包含上述状态修复。候选未覆盖当前 Blender，未发布。

### 2026-09-21 当前客户端重新授权与首次配置链修复

- 当前 Codex CLI 为 `0.153.4`；重新检查时同名 `hyper3d` 仍指向正确地址且保持启用，但当前凭据状态为 `not_logged_in`。此前 `o_auth` 是历史验收事实，不能替代本次连接状态。
- 审计 `/Users/wandl/workspaces/workspace-partme-ai/blender_rodin_bridge_v0.2.0.zip`：参考 Add-on 打开
  `hyper3d.ai?show=plugin` 复用浏览器会话，并通过 `127.0.0.1` WebSocket 转交任务和模型；它没有 OAuth/API Key 客户端实现，且 `rodin_auth` 固定返回 `OK`。PartMe 未复制该无鉴权协议。
- 修复 PartMe 首次 OAuth 只执行 `mcp add` 的缺口：缺失配置执行 `add -> login`，已有同名同地址配置只执行 `login`；只允许自动打开
  `https://api.hyper3d.com/api/grant/oauth/authorize`，不记录临时授权 URL 或 OAuth Token。
- 首次 `codex mcp login hyper3d` 打开的同意页超过有效回调窗口，仍是 `not_logged_in`。随后重新发起授权并完成浏览器同意；CLI 返回 `Successfully logged in`，`codex mcp list` 显示 `hyper3d` 为 `OAuth`，没有覆盖其他 MCP 设置。
- 当前 Codex `0.153.4` 在授权后能够发现 7 个工具：`rodin_create_uploads`、`rodin_generate`、`rodin_generate_bang`、`rodin_get_result`、`rodin_get_status`、`rodin_import_images`、`rodin_wait`；本次只读取会话工具元数据，没有调用生成、提交、下载或付费工具。
- 完整握手仍未通过：发送 `notifications/initialized` 后，Hyper3D 返回 HTTP 202 空响应且缺少 `Content-Type`，Codex 记录 `Unexpected content type: missing-content-type`。因此验收状态是“OAuth 已授权 · 客户端连接待验证”，不能记为 `ready`，上述 7 项只能作为目录发现证据。
- 完整单元回归 `188` 项通过；隔离 Blender 5.2.1 输出
  `NATIVE_HYPER3D_AUTH_MODES={"passed": true, "modes": ["MCP_OAUTH", "API_KEY"], "networkCalls": 0}`。
- 候选 `/tmp/partme-hyper3d-auth.3Eks3n/dist` 的四个发布归档、manifest 与 SBOM 校验全部通过；正式 Add-on 磁盘已逐文件同步，覆盖前备份在
  `/tmp/partme-installed-pre-hyper3d-auth.AhiOvA/partme_blender_mcp`。正式偏好覆盖前后 SHA-256 均为
  `c508066615103b8793b99beff553a11583104928dd1c4d1c1a3fc9c646c5aac2`。
- Blender PID `8822` 未重启，不能把磁盘更新冒充当前内存界面已加载。

## 补充：官方生成提交后台化与偏好恢复

- 新增有界 `ProviderSubmitter`：Rodin API Key 与混元官方提交立即返回本地 `submitting` 任务，网络请求使用已快照的普通配置在后台线程运行，不读取 `bpy`。成功后同一本地任务记录 `remoteTaskId` 与白名单结果引用并进入自动轮询；异常只写脱敏终态。
- 提交中可以本地终止；无法强制中断已发送的供应商 HTTP，但取消后晚到的提交响应、轮询和后续导入都不得复活任务。远端任务 ID 可反查本地取消记录，避免用远端 ID 绕过下载门禁。
- 新增 3 项提交器测试和真实执行适配测试；完整单元回归为 183 项全部通过。候选 `/tmp/partme-background-submit-v2.Aw6kgI/dist` 在 Blender 5.2.1 执行后台提交/轮询验收：1 次慢提交、2 次正常/取消轮询、2 次无效响应查询均在后台，阻塞期间主线程可改帧，付费请求 0。
- 首次重跑模型启停脚本时，隔离配置目录未预创建，Blender 再次把 fixture 偏好写入正式 `userpref.blend`。已立即停止写入，将污染文件保留为 `/private/tmp/partme-enable-flow.mMfHKG/userpref.second-test-write.backup.blend`，并从同一原 Blender PID 8822 在 2026-09-20 成功保存的 `userpref.restored.backup.blend` 恢复。正式文件与恢复副本 SHA-256 均为 `c508066615103b8793b99beff553a11583104928dd1c4d1c1a3fc9c646c5aac2`。
- 测试新增“隔离目录必须在启动 Blender 前真实存在”硬门禁，并显式选择 API Key 模式。随后在 `/tmp/partme-background-submit-v2.Aw6kgI/config-model-v2` 重新执行成功，保存日志全部指向隔离目录；正式偏好哈希前后不变。
- 候选 Add-on 已覆盖到 Blender 5.2 正式 Add-on 目录，覆盖前完整备份在 `/tmp/partme-installed-pre-background-submit.nbqSoM/partme_blender_mcp`；逐文件比较（排除运行缓存）无差异。当前 PID 8822 仍是覆盖前加载的内存模块，场景未保存，未自动重启；磁盘更新不能冒充当前窗口已生效。
- 该证据解决了“生成提交占用主线程”缺口；素材搜索、预览、手动查询和下载的全部网络调用尚未统一后台化，所以广义“所有供应商网络请求不阻塞 UI”门禁仍保持未完成。

## 补充：素材搜索、预览与手动查询后台化

- 新增有界 `ProviderQueryRunner`。Poly Haven 分类/搜索、Sketchfab 搜索/内存预览、Rodin 与混元手动状态查询立即返回 `queryId`，网络只在线程中使用已快照的普通配置，不访问 `bpy`；客户端通过只读 `provider.query_result` 获取完成结果。
- 查询任务增加真实 `querying` 状态；本地终止后晚到结果不写入、不复活任务。结果只接受 JSON 对象，单项最多 8MB、最多缓存 32 项；后台异常统一脱敏为“查询失败或超时”。基础场景查询与 `local_` 本地混元状态不发网络，保持原同步返回。
- TDD 先得到缺少 `provider_queries` 和 `queryId` 的失败，再实现；完整单元回归 `192` 项通过、`5` 项条件跳过，`git diff --check` 通过。
- 候选 `/tmp/partme-background-query.txEn5t/dist` 的四个归档、manifest 与 SBOM 校验全部通过。真实 Blender `5.2.1 LTS` 在隔离配置中请求 Poly Haven，后台返回 `45` 个模型分类：`NATIVE_ASSET_QUERY={"passed":true,"categoryCount":45,"backgroundQuery":true,"communityAddon":false,"paidCalls":0}`；正式偏好哈希前后不变。
- 官方 SDK stdio 握手通过，工具目录为 `177` 项、`4` 页。首次远程矩阵揭示旧已安装 runtime 暴露 `173` 项而候选 HTTP/SSE 暴露 `177` 项；验收脚本随后显式让 stdio 从同一候选加载，避免缓存混用。复跑后 stdio/HTTP/SSE 均为 `177` 项、schema SHA-256 均为 `b566c648851260028d92312155d1130a4e0497d823dbae5002582d6a1ba096c8`。
- loopback HTTP 与自签名 HTTPS 两轮均通过：两个并发 HTTP 客户端与一个 SSE 客户端同时连接，HTTP 断开计数归零后可重连，关闭 HTTP 不影响 SSE；缺失或错误 Bearer Token 均返回 `401`。证据目录分别为 `/tmp/partme-background-query-remote.fnnQfi` 与 `/tmp/partme-background-query-tls.s0TPfl`。
- `asset.fetch_url`、`asset.fetch_generated` 与 Poly Pizza 下载仍会同步下载文件，尚未完成后台传输和进度/终止闭环；因此“全部供应商网络请求不阻塞 UI”总门禁继续保持未完成。

## 补充：素材网络任务后台化与打包后 Blender 验证

- 上一条“素材下载仍同步”的结论已被本节实现取代。公开 MCP 的 `asset.fetch_url`、`asset.fetch_generated`、`asset.polypizza_search`、`asset.polypizza_download` 现在立即返回 `operationId`，统一通过 `asset.operation_result` 轮询；`provider.task_control operation=cancel` 可执行本地终止。
- 下载、短效结果 URL 解析、Poly Pizza API 查询及 ZIP 解压均不在 Blender 主线程执行。供应商凭证和路由先在主线程快照，后台回调移除 `bpy.context` 后仍通过测试；签名 URL 不进入任务回执。
- 本地取消会阻止晚到结果回写，并清除 `.part`、取消中的目标文件和 ZIP 临时解压目录；会话撤销或执行设置重载会关闭旧 registry 的任务执行器。
- 单元回归为 199 项通过、5 项跳过；MCP 公共目录为 173 个命令，包含 `blender_asset_operation_result`。`compileall` 与 `git diff --check` 通过。
- 隔离候选 `/private/tmp/partme-asset-async.axECs7` 的六项 checksum 全部通过，三个 ZIP 通过归档 CRC；runtime ZIP 包含 `asset_transfers.py` 和更新后的 `asset.py`，Add-on ZIP 包含更新后的 `provider_engine.py`。
- 将候选 Add-on 安装到独立 `BLENDER_USER_CONFIG`/`BLENDER_USER_SCRIPTS` 后，Blender 5.2.1 LTS 执行 `native_asset_transfer_smoke.py` 通过：下载线程阻塞期间主线程把帧改为 19，随后本地取消，目标与 `.part` 均不存在，公网/付费调用为 0。
- 同一候选又执行更新后的 `native_local_generation_smoke.py`，本机 HTTP fixture 完成生成→后台暂存→独立事务导入：仅 1 次本机 HTTP、无自动导入、产物 1936 bytes、导入对象 1、场景版本从 0 变为 1，公网/付费调用为 0。
- 候选 runtime ZIP 已安装到隔离 Python 3.13 venv，实际解析并安装官方 `mcp 2.2.0` 及依赖。用该 runtime Python 而非 Blender 内置 Python 执行 stdio 握手，`initialize`、`notifications/initialized`、4 页/178 个无重复工具、只读查询、事务创建/提交、Blender 本地审批、删除重试、回滚和进程退出全部通过。
- 验收脚本现强制 `PARTME_BLENDER_MCP_PYTHON` 指向已安装 runtime venv；Blender 内置 Python 缺少官方 MCP SDK，不再被误当作 stdio 服务运行时。
- 三传输并发验收首次暴露多 Blender 会话下 stdio 自动发现歧义；将 stdio 客户端显式绑定本次 `PARTME_BLENDER_DESCRIPTOR` 后重跑通过。stdio、两个并发 Streamable HTTP、HTTP 重连和 SSE 均连接同一会话，4 页/178 个工具 schema 摘要完全一致；HTTP/SSE 无 Token 和错误 Token 均返回 401，独立停止 HTTP 不影响 SSE，客户端计数归零后可重连，最终撤销会话并卸载 Add-on。
- 隔离 Blender 5.2.1 LTS 的 Rigify 验收通过：检测到内置扩展，`allowDownload=false` 启用并保存隔离偏好，未尝试下载；从真实 human metarig 生成 `RIG-PartMe Rigify MetaRig`，回执包含 221 个新对象。
- `blender-design-plugin` 的 `blender_provider_stage_asset` 已适配异步契约：回执附带 `nextTool=blender_asset_operation_result` 和完整 `providerId/taskId` 参数，不会把 accepted 当作已暂存；该仓库 481 项测试通过、1 项跳过。
- 此证据关闭“供应商网络请求占用 Blender 主线程”源码与 fixture 门禁，但不替代真实 Sketchfab/Poly Pizza/Hyper3D/混元凭证、费用授权、生成质量和真实供应商完整事务导入验收；当前用户前台 Blender 仍未重启加载该候选。
