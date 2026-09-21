## Purpose

为本地和跨机器 Blender MCP 客户端提供可验证、不可误覆盖且能直接传输的视觉证据，并保证截图过程不改变用户场景状态。

## ADDED Requirements

### Requirement: 截图不得改变场景状态
运行时 SHALL 在授权输出目录生成截图，并在成功或失败后恢复活动相机、当前帧、渲染路径、分辨率、比例和文件格式。

#### Scenario: 成功截图后恢复状态
- **WHEN** 客户端调用 `scene.screenshot` 并成功生成图片
- **THEN** 相机、帧和渲染设置与调用前完全一致，场景版本不增加

#### Scenario: 渲染失败后恢复状态
- **WHEN** Blender 渲染操作抛出异常
- **THEN** 运行时仍恢复调用前状态，并且不返回成功回执

### Requirement: 截图必须产生可验证回执
运行时 SHALL 拒绝覆盖已有文件，并为成功截图返回规范路径、媒体类型、字节数、SHA-256、宽高、场景版本和来源命令。

#### Scenario: 新文件生成
- **WHEN** 目标相对路径位于授权输出目录且尚不存在
- **THEN** 运行时生成图片并返回与文件内容一致的回执

#### Scenario: 目标已存在
- **WHEN** 目标路径已经存在
- **THEN** 运行时以明确错误拒绝请求，不修改原文件

### Requirement: 目标图必须锁定
运行时 SHALL 从授权本地路径或有界 Base64 图片创建目标副本，并以 SHA-256、媒体类型、尺寸和字节数锁定；后续轮次不得替换该目标。

#### Scenario: 从远程客户端上传目标图
- **WHEN** 客户端提交受支持且未超过大小上限的 Base64 PNG 或 JPEG
- **THEN** 运行时将内容持久化到该循环的私有目录并返回目标回执

#### Scenario: 非图片或超限上传
- **WHEN** 上传内容的签名、尺寸或大小不符合约束
- **THEN** 运行时在创建循环前拒绝输入且不留下部分文件

### Requirement: 远程客户端必须取得图片内容
MCP 适配器 SHALL 在截图或预览成功结果中附加标准图片内容块，同时保留结构化回执；失败结果不得附加图片内容。

#### Scenario: Streamable HTTP 客户端截图
- **WHEN** 远程客户端成功调用截图工具
- **THEN** 响应同时包含结构化回执和可直接解码的图片内容块

#### Scenario: 图片在返回前被替换
- **WHEN** 适配器读取图片时发现路径越界、哈希不一致或大小超限
- **THEN** 适配器返回安全错误而不发送图片字节

### Requirement: Add-on 与 Runtime 必须协商同一套能力契约
Add-on SHALL 在私有会话描述符中公布产品版本、Harness 协议版本、排序后的命令清单及其 SHA-256；Runtime SHALL 在转发前验证这些字段。

#### Scenario: Add-on 版本过旧
- **WHEN** Runtime 发现描述符缺少版本/能力元数据，或 Add-on 版本与 Runtime 不一致
- **THEN** 调用在发送到 Blender 前以 `ADDON_RUNTIME_VERSION_MISMATCH` 失败，不将底层 `UNKNOWN_COMMAND` 暴露给客户端

#### Scenario: 命令清单被篡改或缺失
- **WHEN** 能力清单哈希不匹配，或客户端调用当前 Add-on 未声明的命令
- **THEN** Runtime 返回明确的能力契约错误且不转发请求

### Requirement: 质量检查必须使用结构化对象定位器
`validation.floor_penetration`、`validation.motion_discontinuity` 和 `validation.prop_handoff` SHALL 把 `object` 声明为对象定位器，与 `ObjectResolver` 的运行时契约一致。

#### Scenario: 以名称检查地面穿插
- **WHEN** 客户端传入 `{"object":{"name":"Hero"}}`
- **THEN** MCP Schema 接受该输入并将定位器原样传给 Harness

#### Scenario: 传入旧字符串参数
- **WHEN** 客户端仅传入 `{"object":"Hero"}`
- **THEN** 请求在 MCP Schema 边界被拒绝，而不是到 Blender 内才失败
