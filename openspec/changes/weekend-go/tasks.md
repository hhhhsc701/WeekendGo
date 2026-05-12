## 1. 项目骨架初始化

- [x] 1.1 创建 `backend/app/__init__.py` 模块入口
- [x] 1.2 创建 `backend/app/core/settings.py` 配置类（OpenAI API key、MCP config路径）
- [x] 1.3 创建 `config/mcp_config.yaml` MCP服务器配置模板
- [x] 1.4 创建 `.env.example` 环境变量模板
- [x] 1.5 创建 `backend/app/main.py` FastAPI应用入口
- [x] 1.6 配置CORS中间件

## 2. MCP集成层

- [x] 2.1 创建 `backend/app/mcp/__init__.py` 模块入口
- [x] 2.2 创建 `backend/app/mcp/config_loader.py` YAML配置加载器
- [x] 2.3 创建 `backend/app/mcp/models.py` MCPServerConfig定义（含mode字段）
- [x] 2.4 创建 `backend/app/mcp/client.py` MCPClientManager连接池
- [x] 2.5 实现API模式调用（_call_api，httpx直接HTTP请求）
- [x] 2.6 实现Local模式调用（_call_local，MCP Server进程通信）
- [x] 2.7 实现统一call方法（根据server.mode自动选择）
- [x] 2.8 实现MCP Server进程生命周期管理（启动/连接池/关闭）
- [x] 2.9 实现超时控制（timeout_seconds配置）
- [x] 2.10 实现错误封装和日志记录
- [x] 2.11 创建 `backend/app/mcp/errors.py` MCPError类型
- [ ] 2.12 验证高德API模式连接
- [ ] 2.13 验证高德Local模式连接（npx MCP Server）
- [ ] 2.14 验证Google Maps API模式连接
- [ ] 2.15 验证Weather MCP连接
- [ ] 2.16 验证12306 MCP连接

## 3. Agent模块

- [x] 3.1 创建 `backend/app/agent/__init__.py` 模块入口
- [x] 3.2 创建 `backend/app/agent/tools.py` TOOL_DEFINITIONS定义
- [x] 3.3 创建 `backend/app/agent/errors.py` AgentError类型
- [x] 3.4 创建 `backend/app/agent/trip_agent.py` TripAgent类骨架
- [x] 3.5 实现ReAct循环主逻辑（run方法）
- [x] 3.6 实现Message History初始化（system + user prompt）
- [x] 3.7 实现工具调用执行（_execute_tool_calls）
- [x] 3.8 实现MCP工具映射（geocode→amap/google, search_poi等）
- [x] 3.9 实现finish工具终止和TripOutput解析
- [x] 3.10 实现max_iterations循环控制

## 4. 数据模型

- [x] 4.1 创建 `backend/app/models/__init__.py` 模块入口
- [x] 4.2 创建 `backend/app/models/trip.py` TripInput定义
- [x] 4.3 创建 `backend/app/models/trip.py` TripOutput定义（Pydantic）
- [x] 4.4 创建 `backend/app/models/trip.py` Place、TripItem、WeatherSummary定义
- [x] 4.5 实现model_validator兼容LLM输出变体

## 5. 数据存储层

- [x] 5.1 创建 `backend/app/db/__init__.py` 模块入口
- [x] 5.2 创建 `backend/app/db/database.py` SQLite连接
- [x] 5.3 创建 `backend/app/db/trip_repository.py` TripRepository类
- [x] 5.4 实现create_trip保存行程
- [x] 5.5 实现get_trip查询行程
- [x] 5.6 实现list_trips列表查询
- [x] 5.7 实现delete_trip删除行程
- [x] 5.8 创建 `backend/scripts/init_db.py` 数据库初始化脚本

## 6. API层

- [x] 6.1 创建 `backend/app/api/__init__.py` 模块入口
- [x] 6.2 创建 `backend/app/api/routes.py` APIRouter定义
- [x] 6.3 实现 POST /api/trips/generate（调用TripAgent）
- [x] 6.4 实现 GET /api/trips/:id（查询行程）
- [x] 6.5 实现 GET /api/trips（行程列表）
- [x] 6.6 实现 DELETE /api/trips/:id（删除行程）
- [x] 6.7 实现 GET /api/config（MCP配置信息）
- [x] 6.8 创建 `backend/app/api/errors.py` 错误处理器
- [x] 6.9 注册AgentError处理器（502/504）

## 7. 前端基础

- [x] 7.1 创建 `frontend/app/layout.tsx` 全局布局
- [x] 7.2 创建 `frontend/app/page.tsx` 首页
- [x] 7.3 创建 `frontend/lib/api.ts` API调用封装
- [x] 7.4 创建 `frontend/types/trip.ts` TypeScript类型定义

## 8. 前端组件

- [x] 8.1 创建 `frontend/components/trip-form.tsx` 输入表单
- [x] 8.2 创建 `frontend/components/timeline-view.tsx` 时间轴展示
- [x] 8.3 创建 `frontend/components/map-view.tsx` 地图可视化（Leaflet）
- [x] 8.4 创建 `frontend/components/itinerary-card.tsx` 行程卡片
- [x] 8.5 创建 `frontend/components/ui/button.tsx` shadcn按钮
- [x] 8.6 创建 `frontend/components/ui/input.tsx` shadcn输入框

## 9. 前端页面

- [x] 9.1 实现首页表单提交流程
- [x] 9.2 创建 `frontend/app/itinerary/[id]/page.tsx` 行程详情页
- [x] 9.3 创建 `frontend/app/history/page.tsx` 历史行程页
- [x] 9.4 实现加载状态和错误提示

## 10. 测试

- [x] 10.1 创建 `backend/tests/test_agent.py` TripAgent测试
- [x] 10.2 实现FakeLLM mock类模拟tool_calls
- [x] 10.3 实现FakeMCP mock类模拟工具结果
- [x] 10.4 测试Agent完整流程（geocode→poi→finish）
- [x] 10.5 测试Agent超时场景
- [x] 10.6 测试工具失败降级场景

## 11. 部署

- [x] 11.1 创建 `scripts/run_backend.sh` 后端启动脚本
- [x] 11.2 创建 `scripts/run_frontend.sh` 前端启动脚本
- [x] 11.3 更新 README.md 使用说明
- [ ] 11.4 验证淮南行程生成
- [ ] 11.5 验证国际城市行程生成