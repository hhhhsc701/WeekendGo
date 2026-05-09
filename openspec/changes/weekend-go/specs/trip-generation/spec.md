## ADDED Requirements

### Requirement: 接收用户输入参数

系统 SHALL 接收以下用户输入参数并验证完整性：

- 城市（必填）：目标行程城市名称
- 日期（必填）：行程日期
- 时长（可选）：行程天数，默认 1 天
- 预算（可选）：总预算金额
- 兴趣标签（必填）：至少选择一个兴趣类型
- 同行人群（必填）：选择人群类型
- 出发城市（可选）：跨城市行程时的出发地
- 备注（可选）：用户补充说明

#### Scenario: 完整输入验证成功

- **WHEN** 用户提交包含所有必填参数的请求
- **THEN** 系统返回验证成功并开始生成行程

#### Scenario: 缺少必填参数

- **WHEN** 用户提交缺少城市或日期的请求
- **THEN** 系统返回 400 错误并提示缺少的参数

### Requirement: 调用 MCP 工具获取地理坐标

系统 SHALL 根据城市区域选择合适的 MCP 工具将城市名称转换为地理坐标。

#### Scenario: 国内城市定位（高德）

- **WHEN** 用户输入城市为"上海"（国内城市）
- **THEN** 系统调用高德 MCP geocode 工具获取坐标 (lat: 31.2304, lng: 121.4737)

#### Scenario: 国外城市定位（Weather MCP）

- **WHEN** 用户输入城市为"Tokyo"（国外城市）
- **THEN** 系统调用 Weather MCP search_location 工具获取坐标

#### Scenario: 小众城市定位失败

- **WHEN** 用户输入城市名无法识别
- **THEN** 系统返回错误并建议用户确认城市名称

### Requirement: 查询天气数据

系统 SHALL 根据坐标和日期查询天气预报，根据区域选择合适的 MCP 工具。

#### Scenario: 国内天气查询（高德）

- **WHEN** 系统获取国内城市坐标和日期
- **THEN** 调用高德 MCP get_weather 工具返回温度、天气状况等信息

#### Scenario: 国外天气查询（Weather MCP）

- **WHEN** 系统获取国外城市坐标和日期
- **THEN** 调用 Weather MCP get_forecast 工具返回温度、降雨概率等信息

#### Scenario: 天气查询失败降级

- **WHEN** 天气工具调用失败
- **THEN** 系统继续生成行程，不包含天气影响因素

### Requirement: 搜索 POI 候选地点

系统 SHALL 根据兴趣标签和城市区域选择合适的 MCP 工具搜索候选地点。

#### Scenario: 国内 POI 搜索（高德）

- **WHEN** 用户选择国内城市"上海"，兴趣标签为"户外"和"美食"
- **THEN** 系统调用高德 MCP search_poi_around 工具搜索周边公园和餐厅

#### Scenario: 国外 POI 搜索（Google Maps）

- **WHEN** 用户选择国外城市"Tokyo"，兴趣标签为"户外"和"美食"
- **THEN** 系统调用 Google Maps MCP maps_search_nearby 工具搜索候选地点

#### Scenario: 搜索结果过滤

- **WHEN** 搜索返回地点
- **THEN** 系统过滤评分低于 4.0 的地点（可配置）

### Requirement: 优化路线顺序

系统 SHALL 根据城市区域选择合适的 MCP 工具优化候选地点的访问顺序。

#### Scenario: 国内路线优化（高德）

- **WHEN** 系统拥有国内城市至少 3 个候选地点坐标
- **THEN** 调用高德 MCP driving_route_planning 工具返回优化后的访问顺序

#### Scenario: 国外路线优化（Google Maps）

- **WHEN** 系统拥有国外城市至少 3 个候选地点坐标
- **THEN** 调用 Google Maps MCP maps_plan_route 工具返回优化后的访问顺序

#### Scenario: 路线优化失败降级

- **WHEN** 路线工具调用失败
- **THEN** 系统按原始顺序排列地点

### Requirement: 查询跨城市交通

系统 SHALL 在用户指定出发城市时，通过 MCP 12306 工具查询火车票信息（仅国内）。

#### Scenario: 国内火车票查询成功

- **WHEN** 用户指定出发城市"北京"和目标城市"上海"（均为国内）
- **THEN** 调用 12306 MCP 返回可选火车班次列表（时间、价格、余票）

#### Scenario: 国外跨城市无火车票查询

- **WHEN** 用户指定出发城市"Beijing"和目标城市"Tokyo"（国外或跨国）
- **THEN** 系统跳过火车票查询，提示无相关交通数据

#### Scenario: 无出发城市

- **WHEN** 用户未指定出发城市
- **THEN** 系统跳过交通查询步骤

### Requirement: LLM 生成结构化行程

系统 SHALL 将所有收集的数据汇总，调用 LLM 生成结构化行程。

#### Scenario: 行程生成成功

- **WHEN** 所有必要数据已收集
- **THEN** LLM 返回 JSON 格式行程，包含时间、地点、活动、花费

#### Scenario: 输出格式验证失败

- **WHEN** LLM 输出不符合预期 JSON 结构
- **THEN** 系统重试最多 3 次，仍失败则返回错误

### Requirement: 返回结构化行程输出

系统 SHALL 返回以下格式的行程数据：

- 行程 ID
- 用户输入参数
- 行程项目列表（时间段、活动、地点、花费、交通）
- 总预算估算
- 天气摘要
- 交通信息（如有）
- 创建时间

#### Scenario: API 返回完整行程

- **WHEN** 行程生成完成
- **THEN** 返回 200 和完整的 TripOutput JSON