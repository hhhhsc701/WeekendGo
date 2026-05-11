## Context

WeekendGo是一个AI周末行程助手，使用ReAct Agent架构让LLM自主决策工具调用。核心挑战：

- **动态决策**：不同城市需要不同工具（国内→高德，国外→Google Maps）
- **策略调整**：工具失败时LLM可尝试其他方案
- **结构化输出**：LLM需输出符合TripOutput格式的行程

## Goals / Non-Goals

**Goals:**
- ReAct Agent自主决策工具调用序列
- Message History管理所有对话和工具结果
- finish工具明确终止循环并输出行程
- 支持国内/国外城市智能判断
- 前后端分离，REST API服务
- SQLite存储行程历史

**Non-Goals:**
- 用户认证系统
- 多语言支持（暂仅中文）
- 移动端原生应用
- 支付/预订功能

## Decisions

### 1. Agent架构：ReAct循环

**决策**：LLM运行Think→Act→Observe循环，自主决策工具调用

```
┌─────────────────────────────────────────────────┐
│                  TripAgent                       │
│                                                  │
│  ReAct Loop:                                     │
│  1. LLM receives messages + tools                │
│  2. LLM outputs: text OR tool_calls OR finish    │
│  3. If tool_calls → execute MCP → append result  │
│  4. If finish → parse TripOutput                 │
│  5. Repeat (max 15 iterations)                   │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐               │
│  │  LLMClient  │  │ MCPManager  │               │
│  │  (OpenAI)   │  │  (Tools)    │               │
│  └─────────────┘  └─────────────┘               │
└─────────────────────────────────────────────────┘
```

**理由**：
- LLM可根据执行结果动态调整策略
- 比固定流程更智能，适应性强
- 无需预定义城市列表

### 2. 工具暴露：OpenAI Function Calling

**决策**：使用tools参数定义MCP工具，LLM通过function calling调用

```python
TOOLS = [
    {"type": "function", "function": {"name": "geocode", ...}},
    {"type": "function", "function": {"name": "search_poi", ...}},
    {"type": "function", "function": {"name": "get_weather", ...}},
    {"type": "function", "function": {"name": "query_trains", ...}},
    {"type": "function", "function": {"name": "finish", ...}},  # 终止信号
]
```

**理由**：
- OpenAI原生支持，格式标准
- 自动参数验证
- tool_calls结构化，易于执行

### 3. 数据管理：Message History

**决策**：使用OpenAI messages数组存储对话+工具结果，不使用独立Context

**理由**：
- OpenAI原生格式
- LLM自然从历史读取数据
- 无需额外存储逻辑

### 4. 终止机制：finish工具

**决策**：finish作为显式工具，LLM调用时输出TripOutput

**理由**：
- 明确终止信号
- 参数定义输出格式
- 防止无限循环

### 5. MCP工具路由：LLM判断

**决策**：LLM通过geocode工具的service参数选择amap或google

**理由**：
- 无需硬编码城市列表
- 工具描述引导：`service: amap(中文城市) | google(英文城市)`
- LLM自主判断

## Risks / Trade-offs

### Risk 1: LLM判断错误

**缓解**：工具描述明确引导 + System Prompt说明

### Risk 2: 调用轮次过多

**缓解**：max_iterations=30上限 + Prompt强调"收集足够信息后立即finish"

### Risk 3: 工具失败

**缓解**：返回错误JSON给LLM，LLM可尝试其他策略或降级生成

## Architecture Layers

| Layer | Tech | Files |
|-------|------|-------|
| Agent | Python + OpenAI | `backend/app/agent/` |
| MCP | Python MCP SDK | `backend/app/mcp/` |
| API | FastAPI | `backend/app/api/` |
| Storage | SQLite | `backend/app/db/` |
| Frontend | Next.js + Tailwind | `frontend/` |

---

## MCP 双模式架构

### 6. MCP调用模式：API vs Local

**决策**：支持两种MCP调用模式，用户通过配置选择

```yaml
# config/mcp_config.yaml
servers:
  amap:
    mode: api  # 直接HTTP调用
    api_url: https://restapi.amap.com/v3
    api_key: ${AMAP_API_KEY}
    
  amap-mcp:
    mode: local  # MCP Server进程
    command: npx
    args: ["-y", "@amap/amap-maps-mcp-server"]
    env:
      AMAP_MAPS_API_KEY: ${AMAP_API_KEY}
```

**理由**：
- API模式：响应快，无需进程管理，适合生产环境
- Local模式：MCP Server封装复杂API逻辑，适合开发/无Key环境
- 用户按需选择，灵活性高

### API模式实现

```python
async def _call_api(self, server: MCPServerConfig, tool: str, params: dict) -> dict:
    """直接HTTP调用远程API"""
    client = httpx.AsyncClient(timeout=server.timeout_seconds)
    url = f"{server.api_url}/{tool}"
    response = await client.get(url, params=params, headers={"key": server.api_key})
    return response.json()
```

**适用**：高德、Google Maps（有官方HTTP API）

### Local模式实现

```python
async def _call_local(self, server: MCPServerConfig, tool: str, params: dict) -> dict:
    """通过MCP Server进程调用"""
    session = await self._get_or_create_session(server)
    result = await session.call_tool(tool, arguments=params)
    return result.content
```

**适用**：Weather MCP、12306 MCP（封装查询逻辑）

### 统一接口

```python
class MCPClientManager:
    async def call(self, server_name: str, tool: str, params: dict) -> dict:
        server = self.config.servers[server_name]
        if server.mode == "api":
            return await self._call_api(server, tool, params)
        return await self._call_local(server, tool, params)
```

Agent无需关心底层模式，统一调用接口。

### 推荐默认配置

| 服务 | 默认模式 | 原因 |
|------|----------|------|
| 高德 | api | 官方HTTP API稳定 |
| Google Maps | api | 官方HTTP API稳定 |
| Weather | local | MCP Server封装便捷 |
| 12306 | local | MCP Server已封装查询逻辑 |