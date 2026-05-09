## Why

周末时间宝贵，但规划行程往往耗时耗力。用户需要根据城市、时间、预算、兴趣和同行人群等维度来安排行程，却常常面临信息分散、决策困难的痛点。

WeekendGo 是一个 AI 周末行程助手，旨在通过智能编排，自动生成个性化周末行程，让用户从繁琐的规划工作中解放出来，专注于享受旅程本身。

## What Changes

- 新增 AI 周末行程生成系统，支持多维度输入参数
- 集成 MCP 工具链（高德 Maps 国内、Google Maps 国外、Weather、12306）获取实时数据
- 实现国内/国外城市智能路由，自动选择合适 MCP 工具链
- 建立前后端分离架构，提供 REST API 服务
- 支持行程生成、调整、保存和查询功能

具体能力：

- **行程生成**: 根据城市、日期、预算、兴趣标签、同行人群类型，自动编排完整行程
- **国内/国外智能路由**: 自动判断城市区域，国内用高德 MCP，国外用 Google Maps MCP
- **天气感知**: 根据天气数据调整活动类型（室内/室外）
- **跨城市交通**: 支持 12306 火车票查询（仅国内），纳入行程考量
- **路线优化**: 基于地理坐标优化行程顺序，减少通勤时间
- **对话调整**: 支持用户通过对话方式微调行程
- **历史记录**: 保存生成的行程，支持查询和复用

## Capabilities

### New Capabilities

- `trip-generation`: 核心行程生成能力 - 接收用户输入，调用 MCP 工具链和 LLM，输出结构化行程
- `mcp-integration`: MCP 工具集成层 - 统一管理高德（国内）、Google Maps（国外）、Weather、12306 等外部数据源，支持区域智能路由
- `trip-management`: 行程管理能力 - 行程保存、查询、列表展示
- `trip-refinement`: 行程调整能力 - 通过对话方式微调已有行程
- `frontend-ui`: 前端用户界面 - 输入表单、行程展示、地图可视化、对话面板

### Modified Capabilities

无（新项目，无既有能力需要修改）

## Impact

### 技术架构

| 层级 | 技术选型                                                    | 说明 |
|------|---------------------------------------------------------|------|
| 前端 | Next.js + React + TypeScript + Tailwind CSS + shadcn/ui | 现代化前端栈，App Router 模式 |
| 后端 | FastAPI + Python 3.12+                                  | 高性能异步 API 服务 |
| MCP 层 | Python MCP SDK (`mcp`)                                  | MCP Client 连接外部工具 |
| LLM 层 | OpenAI SDK (`openai`)                                   | 统一 LLM 调用接口，兼容多种模型 |
| 数据库 | SQLite + sqlite3                                        | 轻量级本地存储 |

### 外部依赖

- **MCP Server**: 
  - `@amap/amap-maps-mcp-server` - 国内城市地点搜索、路线规划、天气查询
  - `mcp-google-map` 或 `@cablate/mcp-google-map` - 国外城市地点搜索、路线规划
  - `weather-mcp` - 国外天气预报（国内可用高德天气）
  - `12306-mcp` - 火车票查询（仅国内）
- **API Keys**:
  - OpenAI API Key（必需）
  - 高德 API Key（必需，用于国内城市）
  - Google Maps API Key（必需，用于国外城市）
  - 12306 无需 Key

### API 端点

```
POST /api/trips/generate     - 生成新行程
POST /api/trips/refine/:id   - 调整现有行程
GET  /api/trips/:id          - 获取行程详情
GET  /api/trips              - 获取行程列表
GET  /api/config             - 获取可用配置信息
```

### 数据模型

- `trips`: 行程记录（输入参数、生成结果、时间戳）
- `trip_items`: 行程具体项目（时间段、活动、地点、花费）