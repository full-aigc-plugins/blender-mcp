# Provider Integration Implementation Plan

**Spec:** `docs/superpowers/specs/2026-09-19-provider-integration-design.md`

## 2026-09-20 收尾门禁（优先于历史勾选项）

当前证据：`docs/verification/ui-function-acceptance-2026-09-20.md`。历史勾选表示历史版本实施，不代表当前构建已发布或全能力通过。

### 当前安装差异门禁（优先处理）

最终候选已覆盖到 Blender 5.2 正式 Add-on 目录，覆盖后逐文件核对无差异；覆盖前安装已备份。当前 Blender 进程仍加载旧模块，且用户场景尚未保存，所以没有自动重启。磁盘一致不等于当前内存实例已更新。

- [ ] 用户保存场景后重新加载完整包，不再仅热替换绘制函数；保留用户偏好、密钥，明确连接重建影响。
- [ ] 重载后核对实际模块来源，再验证三传输、后台生成和事务导入；磁盘逐文件一致性已通过。
- [x] 官方生成提交改为后台本地任务：提交阶段立即返回、主线程可响应、可本地终止，晚到回执不复活任务；真实 Blender fixture 已验证。
- [ ] 用户在 Blender 配置真实供应商，并明确付费验收额度后再进行真实生成；未授权前只允许本机 fixture。
- [x] Hyper3D 增加客户端 OAuth 与 API Key 双模式，刷新时复用 Codex/Claude Code 真实登录状态且不接触 OAuth Token。
- [x] 修复首次客户端 OAuth 只添加不登录的问题：缺失配置执行 `add -> login`，已有同名同地址配置只执行 `login`；仅打开白名单内的 Hyper3D 官方授权 URL。
- [x] 修正 Hyper3D OAuth 状态语义：客户端持有授权但未完成 MCP 握手时不再计为 `ready` 或供应商可用。
- [x] 使用当前 Codex `0.153.4` 完成真实浏览器 OAuth，保留原有 MCP 配置；确认授权后可发现 7 个工具且未调用任何生成能力。
- [x] 用真实 Codex OAuth 客户端完成只读连接、`rodin_get_status` 调用与 7 项工具目录验收；未调用生成或变更工具。初始化仍会出现 HTTP 202 空响应缺少 `Content-Type` 的兼容告警，但当前客户端重试后可用，后续继续跟踪稳定性。
- [x] 正式构建移除独立社区 Add-on 产物，仅发布 PartMe 主 Add-on 与 Runtime/平台包。

- [x] 恢复正式六供应商目录并移除精确的界面演示任务。
- [x] 社区式紧凑供应商行及左侧 HTTP/SSE 控件源码实现。
- [x] 修复失效连接诊断、多会话远程监听绑定、后台 worker 版本混用。
- [x] 补充当前源码命令调用覆盖及真实 Blender/SDK 验证证据。
- [ ] 完成真实外部供应商、Rigify、目标平台及客户端剩余门禁；Rigify 已在隔离 Blender 5.2.1 启用内置扩展并真实生成 221 个控制骨架对象，全程 `allowDownload=false`，剩余真实外部供应商、Windows 和三客户端门禁未完成。
- [ ] 完成最终 UI 和正式安装重启复核。
- [x] 发布 `blender-mcp 0.5.2` 后更新并发布 `blender-design 0.11.2`，同步 runtime lock、插件版本和中央市场 Blender 条目；Codex 安装缓存与 Blender 磁盘 Add-on 已核对。
- [x] 将供应商网络请求移出 Blender 主线程：提交、自动轮询、搜索、预览、手动查询、素材下载及生成结果解析/下载均使用有界后台任务；Blender 5.2.1 打包后 fixture 验证下载阻塞期间主线程可改帧，本地终止清除临时文件且晚到结果不回写。
- [x] 将 Poly Haven/Sketchfab 搜索与预览、Rodin/混元手动状态查询移出 Blender 主线程；新增有界 `provider.query_result`，完成、失败、取消和晚到结果均有确定状态。
- [ ] 完成原生自动轮询调度、取消后的下载/导入阻断以及超时恢复；当前自动轮询、超时失败、下载终止和晚到回执阻断已有单元/真实 Blender fixture，仍需用真实供应商证明完整生成→下载→事务导入链及远端超时恢复，不能以替身或手动查询通过替代。
- [x] 补齐官方混元任务引用到受控暂存的原生解析入口与插件路由（替身测试）。
- [x] 实现本地混元后台生成、查询和受控暂存协议，通过真实 Blender + 本机 HTTP fixture 验证。
- [ ] 使用实际本地混元推理服务验证生成质量、终止和完整事务导入。

- [x] 统一当前版本事实源并增加防漂移测试。
- [x] 新增供应商注册表、状态协议和原生供应商定义。
- [x] 将 Poly Pizza/fetch_url 原生命令迁移到 `blender-mcp`。
- [x] 增加权限、资产库、AI 模型通用 Blender 子面板。
- [x] 按 `docs/design/partme-blender-mcp-sidebar-ui-v1.md` 实现默认展开、自动生成进度、终止生成和完整快捷操作。
- [x] 在插件侧增加社区供应商贡献清单并由自动安装写入 Add-on。
- [x] 移除社区 Poly Pizza 和直接导入公共主路径，增加风险分类。
- [x] 修复 `PluginMcpAdapter` 跨页唯一性并增加真实适配器测试。
- [x] 为 `scripts/harness/` 建立声明式差分门禁。
- [x] 更新活动 README、仓库 URL 和验证状态。
- [x] 构建并验证 `blender-mcp 0.5.2` 最终资产，更新插件 runtime lock。
- [ ] 运行单元、分发、真实 Blender 与客户端矩阵验收；Runtime、隔离 Blender 与 Codex 已通过，ZCode/Kimi 新版本、Windows及前台重启仍待完成。
- [x] 使用 ZCode 0.16.9 自带插件管理器将安装版本更新到 0.11.2，并核对清单、MCP、hook、runtime lock 和 vendored 资产摘要；全新 ZCode CLI 会话协商 MCP `2026-07-28`、发现 183 个工具并真实只读调用 `blender_connection_status` 成功。
- [x] 针对不提供插件管理命令的 Kimi Code CLI 0.43.1，使用活动 `~/.kimi-code` 配置保留原服务器并追加 0.11.2 `partme_blender`，随后由真实 Kimi 会话只读调用 `blender_connection_status` 成功。
- [x] 发布 runtime、插件和市场清单，并记录远端与 Codex/Blender 磁盘安装证据。

## V4.2 真实联动增量

- [x] 为注册表增加独立`enabled/mutable/configurable/toggleLocked`状态、真实可用数和路由门禁测试。
- [x] 将社区供应商启用偏好同步到真实`blendermcp_use_*`属性，并为插件适配器增加禁用门禁。
- [x] 将 Blender 侧栏重构为单工作台四 Tab，保留制作快捷操作和本地审批。
- [x] 增加真实供应商启停 Operator、定向配置入口、busy 锁定和任务终止联动。
- [x] 使用 Blender 用户配置持久化供应商偏好，不把密钥或偏好写入`.blend`。
- [x] 完成定向单元测试、静态 Add-on 合约测试、可复现打包和真实 Blender 供应商启停验收。
- [x] 在可见 Blender UI 中完成`240 px`窄宽度、四 Tab、错误、密钥缺失、生成中和审批截图验收。
- [x] 用官方 MCP Python SDK 替换自写 stdio，并实现真实 Streamable HTTP/SSE 监听器及远程安全设置。
