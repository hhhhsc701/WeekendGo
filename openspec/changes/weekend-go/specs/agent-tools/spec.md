## ADDED Requirements

### Requirement: geocode工具

geocode工具 SHALL 获取城市坐标，LLM通过service参数选择地图服务。

#### Scenario: 工具定义格式

- **WHEN** TOOL_DEFINITIONS加载
- **THEN** geocode包含name、description、parameters
- **AND** parameters定义address(required)、service(optional)

#### Scenario: 中文城市默认amap

- **WHEN** LLM调用geocode传入address="淮南"
- **THEN** 系统调用AMap geocode
- **AND** 返回 `{lat, lng}` 或 `{"geocodes": [{lat, lng}]}`

#### Scenario: 英文城市指定google

- **WHEN** LLM调用geocode传入address="Tokyo" service="google"
- **THEN** 系统调用Google Maps geocode

### Requirement: search_poi工具

search_poi工具 SHALL 搜索附近POI景点。

#### Scenario: 工具定义

- **WHEN** TOOL_DEFINITIONS加载
- **THEN** search_poi包含query(required)、location(optional)、city(optional)

#### Scenario: POI搜索

- **WHEN** LLM调用search_poi传入query="景点" location="lng,lat"
- **THEN** 返回POI列表 `{items: [{name, address, lat, lng, rating}]}`

#### Scenario: 多次搜索

- **WHEN** LLM多次调用search_poi使用不同query
- **THEN** 每次结果独立返回，累积到Message History

### Requirement: get_weather工具

get_weather工具 SHALL 获取城市天气。

#### Scenario: 工具定义

- **WHEN** TOOL_DEFINITIONS加载
- **THEN** get_weather包含city(required)

#### Scenario: 天气查询

- **WHEN** LLM调用get_weather传入city="淮南"
- **THEN** 返回 `{summary, temperature}` 或AMap天气格式

### Requirement: query_trains工具

query_trains工具 SHALL 查询火车班次（仅国内）。

#### Scenario: 工具定义

- **WHEN** TOOL_DEFINITIONS加载
- **THEN** query_trains包含from(required)、to(required)、date(required)

#### Scenario: 火车查询

- **WHEN** LLM调用query_trains传入from="上海" to="淮南" date="2026-05-15"
- **THEN** 返回 `{trains: [{train_no, price}]}`

#### Scenario: 国际城市不支持

- **WHEN** LLM对国际城市调用query_trains
- **THEN** 返回错误或空结果

### Requirement: finish工具

finish工具 SHALL 作为终止信号，LLM输出TripOutput。

#### Scenario: 工具定义

- **WHEN** TOOL_DEFINITIONS加载
- **THEN** finish包含title(required)、items(required)、weather_summary等(optional)

#### Scenario: finish终止

- **WHEN** LLM调用finish传入完整参数
- **THEN** Agent终止循环
- **AND** 参数解析为TripOutput