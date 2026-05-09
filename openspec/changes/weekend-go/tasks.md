## 1. 项目初始化

- [x] 1.1 创建后端项目结构 (FastAPI + Python)
- [x] 1.2 创建前端项目结构 (Next.js + React)
- [x] 1.3 创建配置文件模板 (mcp_config.yaml, .env.example)
- [x] 1.4 初始化 SQLite 数据库结构
- [x] 1.5 编写项目 README 和部署说明

## 2. MCP 集成层

- [x] 2.1 实现配置加载器 (读取 YAML 配置文件)
- [x] 2.2 实现环境变量注入 (支持 ${VAR} 占位符)
- [x] 2.3 实现国内/国外城市判断逻辑 (is_chinese_city)
- [x] 2.4 实现区域路由器 (根据城市选择 MCP 工具链)
- [x] 2.5 实现 MCP Client 管理器 (连接池初始化)
- [x] 2.6 实现统一工具调用接口 (call 方法，支持区域路由)
- [x] 2.7 实现工具调用超时控制
- [x] 2.8 实现错误封装和日志记录
- [ ] 2.9 验证高德 MCP 连接 (国内城市测试)
- [ ] 2.10 验证 Google Maps MCP 连接 (国外城市测试)
- [ ] 2.11 验证 Weather MCP 连接
- [ ] 2.12 验证 12306 MCP 连接 (火车票查询)

## 3. LLM 集成层

- [x] 3.1 实现 LLM Client (OpenAI SDK 封装)
- [x] 3.2 实现 base_url 配置支持 (兼容 DeepSeek 等)
- [x] 3.3 实现行程生成提示词模板
- [x] 3.4 实现调整意图解析提示词模板
- [x] 3.5 实现 JSON 输出强制 (function calling 或格式约束)
- [x] 3.6 实现输出验证和重试逻辑

## 4. 行程生成核心

- [x] 4.1 实现用户输入验证 (Pydantic schema)
- [x] 4.2 实现区域判断步骤 (is_chinese_city 判断国内/国外)
- [x] 4.3 实现国内城市定位步骤 (调用高德.geocode)
- [x] 4.4 实现国外城市定位步骤 (调用 weather.search_location)
- [x] 4.5 实现国内天气查询步骤 (调用高德.get_weather)
- [x] 4.6 实现国外天气查询步骤 (调用 weather.get_forecast)
- [x] 4.7 实现兴趣→POI类型映射逻辑
- [x] 4.8 实现国内 POI 搜索步骤 (调用高德.search_poi_around)
- [x] 4.9 实现国外 POI 搜索步骤 (调用 google-maps.maps_search_nearby)
- [x] 4.10 实现 POI 结果过滤逻辑 (评分、距离)
- [x] 4.11 实现国内路线优化步骤 (调用高德.driving_route_planning)
- [x] 4.12 实现国外路线优化步骤 (调用 google-maps.maps_plan_route)
- [x] 4.13 实现火车票查询步骤 (调用 12306.query_trains，仅国内跨城市)
- [x] 4.14 实现完整行程编排流程 (双路径统一)
- [x] 4.15 实现 TripOutput 结构化输出解析

## 5. 行程调整功能

- [x] 5.1 实现调整请求接收和验证
- [x] 5.2 实现调整意图解析 (LLM)
- [x] 5.3 实现调整执行逻辑 (时间重排、地点更换等)
- [x] 5.4 实现调整冲突检测和处理
- [x] 5.5 实现调整历史记录

## 6. 数据存储层

- [x] 6.1 实现数据库连接 (sqlite3)
- [x] 6.2 实现 trips 表模型定义
- [x] 6.3 实现行程保存 CRUD
- [x] 6.4 实现行程查询 CRUD (单个、列表)
- [x] 6.5 实现行程更新 CRUD
- [x] 6.6 实现行程删除 CRUD

## 7. API 层

- [x] 7.1 实现 FastAPI 应用入口
- [x] 7.2 实现 CORS 中间件配置
- [x] 7.3 实现 POST /api/trips/generate 端点
- [x] 7.4 实现 POST /api/trips/refine/:id 端点
- [x] 7.5 实现 GET /api/trips/:id 端点
- [x] 7.6 实现 GET /api/trips 端点
- [x] 7.7 实现 GET /api/config 端点
- [x] 7.8 实现统一错误处理
- [x] 7.9 实现 API 文档 (自动生成或手写)

## 8. 前端基础

- [x] 8.1 初始化 Next.js 项目 (App Router)
- [x] 8.2 配置 Tailwind CSS
- [x] 8.3 安装配置 shadcn/ui 组件库
- [x] 8.4 实现全局布局组件
- [x] 8.5 实现 API 调用封装 (lib/api.ts)
- [x] 8.6 定义前端 TypeScript 类型 (types/)

## 9. 前端组件

- [x] 9.1 实现 TripForm 输入表单组件
- [x] 9.2 实现 TripForm 字段验证
- [x] 9.3 实现 ItineraryCard 行程卡片组件
- [x] 9.4 实现 TimelineView 时间轴组件
- [x] 9.5 实现 MapView 地图可视化组件 (Leaflet)
- [x] 9.6 实现 ChatPanel 对话调整组件
- [x] 9.7 实现历史行程列表组件
- [x] 9.8 实现加载状态和错误提示组件

## 10. 前端页面

- [x] 10.1 实现首页 (TripForm + 生成触发)
- [x] 10.2 实现行程详情页 (ItineraryCard + MapView)
- [x] 10.3 实现调整对话页 (ChatPanel)
- [x] 10.4 实现历史行程页
- [x] 10.5 实现响应式布局适配
- [x] 10.6 实现页面路由配置

## 11. 集成测试

- [x] 11.1 测试国内行程生成流程 (上海周末，使用高德 MCP)
- [x] 11.2 测试国外行程生成流程 (东京周末，使用 Google Maps MCP)
- [x] 11.3 测试天气影响活动选择 (国内/国外)
- [x] 11.4 测试跨城市火车票查询 (北京→上海)
- [x] 11.5 测试行程调整对话
- [x] 11.6 测试前端表单提交到展示完整流程
- [x] 11.7 测试错误场景处理 (工具超时、LLM 失败)
- [x] 11.8 测试区域边界情况 (模糊城市名识别)

## 12. 部署准备

- [x] 12.1 编写后端启动脚本
- [x] 12.2 编写前端启动脚本
- [x] 12.3 编写 Docker 配置 (可选)
- [x] 12.4 编写部署文档和配置说明
- [x] 12.5 准备示例配置文件供用户参考
