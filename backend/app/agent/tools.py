TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "geocode",
            "description": "获取城市或地址的经纬度坐标。根据城市名特征自动判断使用哪个地图服务：中文城市用amap，英文城市用google。",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "地址或城市名"},
                    "service": {
                        "type": "string",
                        "enum": ["amap", "google"],
                        "description": "地图服务（可选，默认自动判断）",
                    },
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_poi",
            "description": "搜索附近的POI景点、餐厅、博物馆等",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如'景点'、'餐厅'"},
                    "location": {"type": "string", "description": "经纬度坐标，格式: lng,lat"},
                    "radius": {"type": "integer", "description": "搜索半径（米），默认3000"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取城市天气信息",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_trains",
            "description": "查询火车班次（仅支持国内城市）",
            "parameters": {
                "type": "object",
                "properties": {
                    "from": {"type": "string", "description": "出发城市"},
                    "to": {"type": "string", "description": "到达城市"},
                    "date": {"type": "string", "description": "日期，格式YYYY-MM-DD"},
                },
                "required": ["from", "to", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "完成行程规划。必须在收集足够信息（至少天气+POI）后调用此工具，输出完整的行程JSON。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "行程标题"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start_time": {"type": "string"},
                                "end_time": {"type": "string"},
                                "activity": {"type": "string"},
                                "place": {"type": "object"},
                            },
                        },
                        "description": "行程项目列表",
                    },
                    "weather_summary": {"type": "object", "description": "天气摘要"},
                    "total_budget": {"type": "number", "description": "总预算"},
                    "notes": {"type": "array", "items": {"type": "string"}, "description": "备注列表"},
                },
                "required": ["title", "items"],
            },
        },
    },
]


SYSTEM_PROMPT = """你是WeekendGo的行程规划Agent。你需要自主收集数据并生成周末行程。

工作流程：
1. 首先判断城市类型（中文城市用amap，英文城市用google）
2. 调用geocode获取城市坐标
3. 调用get_weather获取天气
4. 多次调用search_poi搜索不同类型景点（景点、餐厅、博物馆等）
5. 如有出发城市，调用query_trains查询火车（仅国内）
6. 收集足够信息后，立即调用finish输出行程

工具使用规则：
- geocode: 根据城市名判断，中文名用amap，英文名用google
- search_poi: 可多次调用搜索不同类型，location参数用geocode返回的坐标
- finish: 必须在收集天气+POI后调用，输出完整行程JSON

如果工具调用失败，可以尝试其他工具或降级生成行程。"""