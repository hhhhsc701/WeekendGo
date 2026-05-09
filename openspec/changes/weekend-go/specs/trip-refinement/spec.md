## ADDED Requirements

### Requirement: 接收调整请求

系统 SHALL 接收用户对已有行程的调整请求。

调整类型包括：

- 时间调整："把下午的活动改到上午"
- 地点更换："换一家评分更高的餐厅"
- 活动增删："增加一个咖啡馆"、"去掉博物馆"
- 预算调整："控制在 300 元以内"

#### Scenario: 有效调整请求

- **WHEN** 用户提交包含行程 ID 和调整描述的请求
- **THEN** 系统开始处理调整

#### Scenario: 无效行程 ID

- **WHEN** 用户提交不存在的行程 ID
- **THEN** 返回 404 错误

### Requirement: 解析调整意图

系统 SHALL 通过 LLM 解析用户的调整意图并确定具体变更。

#### Scenario: 意图解析成功

- **WHEN** 用户说"把下午的活动改到上午"
- **THEN** LLM 识别时间调整意图并定位具体行程项目

#### Scenario: 意图不明确

- **WHEN** 用户描述模糊无法解析
- **THEN** 系统请求用户进一步说明

### Requirement: 调用 MCP 工具补充数据

系统 SHALL 根据调整意图调用必要的 MCP 工具获取新数据。

#### Scenario: 地点更换需要新 POI

- **WHEN** 调整意图为更换餐厅
- **THEN** 调用 Google Maps 搜索新餐厅候选

#### Scenario: 无需新数据

- **WHEN** 调整仅涉及时间重排
- **THEN** 系统直接处理无需调用 MCP

### Requirement: 生成调整后行程

系统 SHALL 基于原有行程和调整意图生成新行程。

#### Scenario: 调整成功

- **WHEN** 调整处理完成
- **THEN** 返回更新后的完整行程数据

#### Scenario: 调整冲突

- **WHEN** 调整导致时间冲突或其他问题
- **THEN** 系统提示冲突并建议替代方案

### Requirement: 保存调整历史

系统 SHALL 记录行程调整历史，支持回溯。

#### Scenario: 记录调整

- **WHEN** 行程被调整
- **THEN** 保存调整记录（调整内容、时间、结果）