## Why

周末行程规划需要整合多源数据（地图POI、天气、交通），但不同城市数据源不同（国内用高德、国外用Google Maps），且数据获取策略需根据实际情况动态调整（如POI失败后尝试其他关键词）。

传统固定流程无法适应这种动态决策需求，需要让LLM作为Agent自主判断城市类型、选择工具、调整策略。

## What Changes

- **新增 ReAct TripAgent** - LLM自主决策MCP工具调用，Think→Act→Observe循环
- **新增 TOOL_DEFINITIONS** - OpenAI Function Calling工具定义（geocode、search_poi、get_weather、query_trains、finish）
- **新增 FastAPI后端** - 提供 REST API 服务
- **新增 Next.js前端** - 用户界面（输入表单、行程展示、地图可视化）
- **新增 SQLite存储** - 行程历史记录
- **新增 MCP工具链双模式** - API模式（直接HTTP调用）+ Local模式（MCP Server进程）

**核心能力**：
- LLM根据城市名特征自主判断国内/国际
- LLM自主决定工具调用顺序和参数
- 工具失败时LLM可调整策略
- LLM通过finish工具输出结构化行程

## Capabilities

### New Capabilities

- `trip-agent`: ReAct Agent核心 - LLM自主决策工具调用序列
- `agent-tools`: Function Calling工具定义（5个工具）
- `mcp-integration`: MCP工具集成（高德、Google Maps、Weather、12306）
- `trip-api`: FastAPI REST API服务
- `trip-frontend`: Next.js用户界面
- `trip-storage`: SQLite行程存储

## Impact

**架构**：
```
TripAgent (ReAct Loop)
    ├─ LLMClient (OpenAI)
    ├─ MCPManager (工具池)
    └─ MessageHistory (对话+工具结果)

FastAPI
    └─ POST /api/trips/generate → TripAgent.run()

Next.js
    └─ TripForm → API → TripOutput → TimelineView
```

**外部依赖**：
- OpenAI API（LLM决策）
- 高德 API（国内城市）
- Google Maps API（国外城市）
- Weather MCP
- 12306 MCP（火车票）