## ADDED Requirements

### Requirement: 配置文件加载

系统 SHALL 从 YAML 配置文件加载 MCP Server 配置信息，支持国内（高德）和国外（Google Maps）双路由配置。

#### Scenario: 配置文件存在且有效

- **WHEN** 应用启动时找到有效配置文件
- **THEN** 系统解析配置并准备初始化 MCP Server（高德、Google Maps、Weather、12306）

#### Scenario: 配置文件缺失

- **WHEN** 配置文件不存在
- **THEN** 系统返回错误并提示需要配置文件

### Requirement: 国内/国外城市判断

系统 SHALL 根据用户输入的城市名称判断使用国内（高德 MCP）或国外（Google Maps MCP）工具链。

#### Scenario: 国内城市识别

- **WHEN** 用户输入城市为"上海"、"北京"等中国城市
- **THEN** 系统判定为国内城市，使用高德 MCP 工具链

#### Scenario: 国外城市识别

- **WHEN** 用户输入城市为"Tokyo"、"Paris"、"New York"等国外城市
- **THEN** 系统判定为国外城市，使用 Google Maps MCP 工具链

#### Scenario: 城市识别模糊

- **WHEN** 用户输入城市名称无法明确判断国内/国外
- **THEN** 系统默认使用高德 MCP（中文输入优先国内），并提供用户确认选项

### Requirement: MCP Server 连接管理

系统 SHALL 在应用启动时初始化配置中启用的 MCP Server 连接。

#### Scenario: 多 Server 连接成功

- **WHEN** 配置启用 amap（高德）、google-maps、weather、12306 四个 Server
- **THEN** 系统成功建立所有连接并记录可用工具列表

#### Scenario: 单 Server 连接失败

- **WHEN** google-maps Server 启动失败（如缺少 API Key）
- **THEN** 系统记录错误，其他 Server（高德）继续运行，国外行程降级处理

### Requirement: 高德 MCP 工具集成

系统 SHALL 集成高德地图 MCP Server，提供国内城市的地理信息服务。

高德 MCP 提供的工具：
- `geocode`: 地理编码（地址→坐标）
- `search_poi`: POI 关键字搜索
- `search_poi_around`: 周边 POI 搜索
- `driving_route_planning`: 驾车路线规划
- `walking_route_planning`: 步行路线规划
- `public_transit_route_planning`: 公交路线规划
- `get_weather`: 天气查询
- `search_poi_detail`: POI 详情查询

#### Scenario: 高德 MCP 连接成功

- **WHEN** 配置提供有效的高德 API Key
- **THEN** 系统连接高德 MCP Server 并注册所有工具

#### Scenario: 高德 API Key 无效

- **WHEN** 高德 API Key 无效或缺失
- **THEN** 系统返回错误并提示需要配置高德 API Key

### Requirement: Google Maps MCP 工具集成

系统 SHALL 集成 Google Maps MCP Server，提供国外城市的地理信息服务。

#### Scenario: Google Maps MCP 连接成功

- **WHEN** 配置提供有效的 Google Maps API Key
- **THEN** 系统连接 Google Maps MCP Server 并注册所有工具

#### Scenario: Google Maps API Key 无效

- **WHEN** Google Maps API Key 无效或缺失
- **THEN** 系统记录警告，国外行程将降级处理

### Requirement: 统一工具调用接口（区域路由）

系统 SHALL 提供统一的工具调用方法，根据区域自动路由到对应 MCP Server。

#### Scenario: 国内城市调用高德工具

- **WHEN** 业务代码调用 `mcp.call("domestic", "search_poi_around", params)`
- **THEN** 系统路由到高德 MCP 执行 search_poi_around 并返回结果

#### Scenario: 国外城市调用 Google Maps 工具

- **WHEN** 业务代码调用 `mcp.call("international", "maps_search_nearby", params)`
- **THEN** 系统路由到 Google Maps MCP 执行并返回结果

#### Scenario: 工具不存在

- **WHEN** 调用未注册的工具名称
- **THEN** 系统返回错误提示工具不可用

### Requirement: 工具调用超时控制

系统 SHALL 对每个 MCP 工具调用设置超时限制。

#### Scenario: 工具正常响应

- **WHEN** 工具在超时时间内返回
- **THEN** 正常返回结果

#### Scenario: 工具超时

- **WHEN** 工具调用超过超时时间（默认 30 秒）
- **THEN** 系统取消调用并返回超时错误

### Requirement: 工具调用错误封装

系统 SHALL 统一封装 MCP 工具调用错误，不暴露底层细节。

#### Scenario: MCP 内部错误

- **WHEN** MCP Server 返回内部错误
- **THEN** 系统封装为标准错误格式返回给调用者

### Requirement: 环境变量注入

系统 SHALL 支持配置文件中使用环境变量占位符。

#### Scenario: API Key 从环境变量读取

- **WHEN** 配置写为 `AMAP_API_KEY: ${AMAP_API_KEY}` 或 `GOOGLE_MAPS_API_KEY: ${GOOGLE_MAPS_API_KEY}`
- **THEN** 系统从环境变量读取实际值注入配置

#### Scenario: 环境变量未设置

- **WHEN** 配置引用的环境变量未设置
- **THEN** 系统返回配置错误提示