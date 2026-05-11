## ADDED Requirements

### Requirement: TripAgent ReAct循环

系统 SHALL 提供TripAgent类实现ReAct循环，LLM自主决策MCP工具调用。

#### Scenario: 基本Agent执行

- **WHEN** 用户提交行程请求（城市、日期、兴趣）
- **THEN** Agent启动ReAct循环
- **AND** LLM输出tool_calls
- **AND** 系统执行MCP工具并返回结果
- **AND** LLM继续决策直到调用finish

#### Scenario: 超过最大轮次

- **WHEN** Agent执行超过15轮
- **THEN** 系统抛出AgentTimeoutError
- **AND** API返回504错误

### Requirement: TOOL_DEFINITIONS工具定义

系统 SHALL 定义5个Function Calling工具供LLM调用。

#### Scenario: 工具列表完整

- **WHEN** Agent初始化
- **THEN** tools包含：geocode、search_poi、get_weather、query_trains、finish
- **AND** 每个工具符合OpenAI格式

### Requirement: geocode工具获取坐标

geocode工具 SHALL 获取城市坐标，LLM自主选择service参数。

#### Scenario: 中文城市选amap

- **WHEN** LLM调用geocode传入address="淮南"
- **THEN** 系统默认调用AMap geocode
- **AND** 返回坐标

#### Scenario: 英文城市选google

- **WHEN** LLM调用geocode传入address="Tokyo" service="google"
- **THEN** 系统调用Google Maps geocode

### Requirement: search_poi工具搜索景点

search_poi工具 SHALL 搜索附近POI。

#### Scenario: POI搜索成功

- **WHEN** LLM调用search_poi传入query="景点" location="lng,lat"
- **THEN** 返回POI列表

#### Scenario: POI搜索失败降级

- **WHEN** POI搜索返回空或失败
- **THEN** LLM可选择尝试其他关键词或降级生成

### Requirement: finish工具输出行程

finish工具 SHALL 作为终止信号，LLM输出TripOutput。

#### Scenario: 正常finish

- **WHEN** LLM调用finish传入title、items
- **THEN** Agent解析为TripOutput
- **AND** 返回完整行程

### Requirement: Message History管理

Agent SHALL 使用messages数组存储对话和工具结果。

#### Scenario: 工具结果加入历史

- **WHEN** MCP工具执行完成
- **THEN** 结果以role="tool"加入messages
- **AND** LLM下轮可读取

### Requirement: API端点

系统 SHALL 提供REST API服务。

#### Scenario: 生成行程API

- **WHEN** POST /api/trips/generate
- **THEN** 返回TripOutput JSON

#### Scenario: 查询行程API

- **WHEN** GET /api/trips/:id
- **THEN** 返回已保存行程