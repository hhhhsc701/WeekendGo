## Context

WeekendGo 是一个全新项目，当前代码库为空（仅有配置文件）。项目目标是构建一个 AI 周末行程助手，核心挑战在于：

- **数据集成复杂**: 需要整合多个外部数据源（地图、天气、交通）
- **AI 编排挑战**: 如何让 LLM 有效调用 MCP 工具并生成合理行程
- **前后端协作**: 异构技术栈（React + Python）需要良好的 API 设计
- **配置驱动**: 用户可能更换 LLM 提供商或 MCP 工具组合

## Goals / Non-Goals

**Goals:**

1. 建立可扩展的 MCP 工具集成层，支持配置化添加/移除工具
2. 实现统一的 LLM 调用接口，支持 OpenAI 及兼容 API
3. 构建清晰的前后端 API 契约，确保数据流顺畅
4. 完成核心行程生成流程，从用户输入到结构化输出
5. 提供直观的前端界面，支持输入、展示、调整和保存

**Non-Goals:**

1. 用户认证系统（暂不实现登录）
2. 多语言支持（暂仅中文）
3. 移动端原生应用（仅 Web）
4. 实时多人协作编辑
5. 支付/预订功能（仅生成建议，不执行交易）

## Decisions

### 1. 技术栈选择

| 决策 | 选型 | 原因 |
|------|------|------|
| 前端框架 | Next.js App Router | React 生态成熟，App Router 提供更好的 DX |
| 后端框架 | FastAPI | Python 原生异步支持，MCP SDK Python 版本完善 |
| 数据库 | SQLite | MVP 阶段零配置，单文件便于备份迁移 |
| LLM SDK | OpenAI SDK | 统一接口，通过 base_url 兼容 DeepSeek/本地模型 |

**备选方案考虑:**

- Node.js 后端 → 虽 TypeScript SDK 完善，但 Python MCP SDK 同样成熟，且 FastAPI 性能足够
- PostgreSQL → 增加部署复杂度，MVP 阶段 SQLite 足够
- LangChain → 学习曲线陡峭，直接用 MCP SDK 更可控

### 2. MCP 架构设计（国内/国外双路由）

系统根据目标城市自动选择合适的 MCP 工具链：

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client Manager                       │
│                                                             │
│  ┌─────────────┐                                            │
│  │ Config      │ ──读取──▶ mcp_config.yaml                  │
│  │ Loader      │                                            │
│  └─────────────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │ Region      │ ──判断──▶ 国内城市？国外城市？             │
│  │ Router      │                                            │
│  └─────────────┘                                            │
│         │                                                    │
│    ┌────┴────┐                                              │
│    ▼         ▼                                              │
│ ┌──────┐  ┌──────┐                                          │
│ │国内  │  │国外  │                                          │
│ │路由  │  │路由  │                                          │
│ └──────┘  └──────┘                                          │
│    │         │                                              │
│    ▼         ▼                                              │
│ ┌──────┐  ┌──────┐                                          │
│ │高德  │  │Google│                                          │
│ │MCP   │  │Maps  │                                          │
│ │      │  │MCP   │                                          │
│ └──────┘  └──────┘                                          │
│                                                             │
│  共享工具:                                                   │
│  ├── weather-mcp (天气查询，国内外通用)                      │
│  ├── 12306-mcp (火车票查询，仅国内跨城市)                    │
│  └─────────────────────────────────────────────────────    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**国内/国外判断逻辑:**

```python
# 城市判断逻辑
CHINESE_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", 
    "西安", "南京", "苏州", "重庆", "天津", "长沙", "青岛",
    "厦门", "昆明", "大连", "三亚", "桂林", "丽江",
    # ... 更多中国城市
]

def is_chinese_city(city_name: str) -> bool:
    """判断是否为中国城市"""
    # 方式1: 直接匹配城市名
    if city_name in CHINESE_CITIES:
        return True
    # 方式2: 检查是否包含中文且不在已知国外城市列表
    if contains_chinese(city_name):
        return True
    return False
```

**MCP 工具映射:**

| 功能 | 国内城市 | 国外城市 |
|------|---------|---------|
| 地理编码 | 高德 `geocode` | Google Maps `geocode` |
| POI 搜索 | 高德 `search_poi` / `search_poi_around` | Google Maps `maps_search_nearby` |
| 路线规划 | 高德 `driving_route_planning` 等 | Google Maps `maps_plan_route` |
| 天气查询 | 高德 `get_weather` 或 weather-mcp | weather-mcp |
| 火车票查询 | 12306-mcp | 不适用 |

**关键设计:**

- MCP Server 在应用启动时初始化，连接池管理
- 根据城市自动路由到对应 MCP 工具链
- 工具调用通过统一 `call(region, tool, params)` 方法
- 配置文件支持启用/禁用特定 Server
- 错误处理统一封装，单个工具失败不影响整体流程

### 3. 行程生成流程（国内/国外双路径）

```
用户输入
    │
    ▼
Step 0: 区域判断 ──────────▶ is_chinese_city(城市名)?
    │                           → 确定使用哪个 MCP 工具链
    ▼
    ├───────────────────────┬───────────────────────┐
    │                       │                       │
    ▼ (国内)                ▼ (国外)                │
                                                            │
Step 1: 定位               Step 1: 定位                 │
    │ 高德.geocode()           │ weather-mcp.search_location()│
    │ → 获取城市坐标           │ → 获取城市坐标           │
    ▼                          ▼                          │
                                                            │
Step 2: 天气               Step 2: 天气                 │
    │ 高德.get_weather()       │ weather-mcp.get_forecast() │
    │ 或 weather-mcp           │ → 决定室内/室外倾向       │
    │ → 决定室内/室外倾向       ▼                          │
    ▼                                                      │
                                                            │
Step 3: POI 搜索           Step 3: POI 搜索             │
    │ 高德.search_poi_around() │ google-maps.maps_search_   │
    │ → 根据兴趣获取候选地点   │   nearby()                  │
    │                         │ → 根据兴趣获取候选地点     │
    ▼                          ▼                          │
                                                            │
Step 4: 路线优化           Step 4: 路线优化             │
    │ 高德.driving_route_      │ google-maps.maps_plan_    │
    │   planning()             │   route()                  │
    │ → 优化访问顺序           │ → 优化访问顺序           │
    ▼                          ▼                          │
                                                            │
Step 5: 交通查询 (仅国内跨城市)  Step 5: 无                  │
    │ 12306-mcp.query_trains() │                           │
    │ → 火车票信息             │                           │
    ▼                          │                           │
    │                          │                           │
    └───────────────────────┴───────────────────────┘
                    │
                    ▼
Step 6: LLM 编排 ──────────▶ openai.chat.completions.create()
    │                           → 综合数据生成行程
    ▼
结构化输出 (JSON)
```

**关键设计:**

- 各步骤独立封装，可单独测试
- 根据城市自动选择 MCP 工具链（国内用高德，国外用 Google Maps）
- 高德 MCP 提供 12+ 工具，覆盖 POI 搜索、路线规划、天气查询等
- LLM 提示词模板化，包含完整上下文
- 输出强制 JSON 格式，便于后续处理

### 4. 前端架构

```
┌─────────────────────────────────────────────────────────────┐
│                       Next.js App                           │
│                                                             │
│  app/                                                       │
│  ├── layout.tsx         全局布局                            │
│  ├── page.tsx           首页 - TripForm                     │
│  ├── itinerary/[id]/    行程详情 - ItineraryCard + MapView  │
│  ├── chat/[id]/         调整对话 - ChatPanel                 │
│  └── history/           历史行程列表                         │
│                                                             │
│  components/                                                │
│  ├── ui/                 shadcn/ui 组件                     │
│  ├── trip-form.tsx       输入表单                           │
│  ├── itinerary-card.tsx  行程卡片                           │
│  ├── timeline-view.tsx   时间轴视图                         │
│  ├── map-view.tsx        地图可视化                         │
│  └───────────────────────────────────────────────────────  │
│                                                             │
│  lib/                                                       │
│  ├── api.ts              API 调用封装                       │
│  └───────────────────────────────────────────────────────  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**关键设计:**

- App Router 模式，路由清晰
- shadcn/ui 提供 UI 基础，Tailwind 定制样式
- API 调用集中封装，便于处理错误和缓存

### 5. 数据模型

```python
# trips 表
id: str              # UUID
input_json: str      # TripInput JSON
output_json: str     # TripOutput JSON  
created_at: datetime # 创建时间
updated_at: datetime # 更新时间
```

**设计考量:**

- MVP 阶段采用 JSON 存储，避免复杂关联
- 后续可拆分为 trips + trip_items 两表
- 不存储用户 ID（暂无认证）

## Risks / Trade-offs

### 风险 1: MCP 工具稳定性

**风险**: MCP Server 可能因网络/依赖问题失败
**缓解**: 
- 每个工具调用独立超时控制
- 核心工具失败时降级处理（用 LLM 知识补充）
- 错误日志记录，便于排查

### 风险 2: LLM 输出不确定性

**风险**: LLM 可能生成格式不符或内容不合理的行程
**缓解**:
- 强制 JSON 输出格式，使用 function calling
- 后端验证输出结构，不合格则重试（最多 3 次）
- 关键字段必填校验（时间、地点）

### 风险 3: API Key 管理

**风险**: API Key 泄露或费用失控
**缓解**:
- 后端统一管理 Key，不暴露给前端
- 配置文件示例使用环境变量占位符
- 建议用户设置 OpenAI 使用限额

### 风险 4: 跨域部署

**风险**: 前后端分离部署可能面临 CORS 问题
**缓解**:
- FastAPI 配置 CORS 中间件
- 开发环境统一 localhost
- 生产环境建议同域部署

## Migration Plan

无迁移需求（新项目）。

部署步骤:

1. 配置环境变量（API Keys）
2. 启动后端: `uvicorn app.main:app`
3. 启动前端: `npm run dev`
4. 验证 MCP 连接和 LLM 调用

## Open Questions

1. **行程持久化策略**: JSON 存储是否足够？是否需要拆分为多表？
   - 建议: MVP 用 JSON，后续根据需求演进

2. **前端地图组件**: Leaflet vs Google Maps React SDK？
   - 建议: Leaflet（免费，无需额外 Key）

3. **用户输入验证**: 前端还是后端做？
   - 建议: 双端验证，后端为主（Pydantic schema）

4. **并发请求处理**: 多用户同时生成行程时 MCP 连接池如何管理？
   - 建议: 单例 MCP Client，异步锁保护关键操作