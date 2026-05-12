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
                                "place": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "address": {"type": "string"},
                                        "coordinates": {
                                            "type": "object",
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "required": ["lat", "lng"],
                                        },
                                        "category": {"type": "string"},
                                    },
                                    "required": ["name"],
                                },
                                "estimated_cost": {
                                    "type": "number",
                                    "description": "本步骤预计花费，人民币元。免费项目填0。",
                                },
                                "transport": {"type": "string"},
                                "transport_detail": {
                                    "type": "object",
                                    "description": "具体火车或飞机信息。只有存在明确车次/航班时填写。",
                                    "properties": {
                                        "mode": {
                                            "type": "string",
                                            "description": "train或flight",
                                        },
                                        "code": {
                                            "type": "string",
                                            "description": "车次或航班号，如G1234、MU2527",
                                        },
                                        "departure": {
                                            "type": "string",
                                            "description": "出发站/机场",
                                        },
                                        "arrival": {
                                            "type": "string",
                                            "description": "到达站/机场",
                                        },
                                        "departure_coordinates": {
                                            "type": "object",
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "description": "出发站/机场坐标",
                                        },
                                        "arrival_coordinates": {
                                            "type": "object",
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "description": "到达站/机场坐标",
                                        },
                                        "departure_time": {"type": "string"},
                                        "arrival_time": {"type": "string"},
                                        "duration": {"type": "string"},
                                        "cost": {
                                            "type": "number",
                                            "description": "该车次/航班费用，人民币元",
                                        },
                                    },
                                },
                                "notes": {"type": "string"},
                            },
                            "required": ["start_time", "end_time", "activity", "place", "estimated_cost"],
                        },
                        "description": "行程项目列表。每个项目必须尽量包含地点坐标和本步骤预算。",
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
- finish.items: 每一步必须填写estimated_cost；免费项目填0，不要省略。
- finish.items.place: 优先使用search_poi返回的真实地点名称、地址和坐标；coordinates格式为{"lat": 纬度, "lng": 经度}。国内高德location为"lng,lat"，需要转换成lat/lng字段。
- finish.items.transport_detail: 如果步骤包含具体车次或航班，必须填写mode、code、departure、arrival、departure_time、arrival_time、cost；如知道出发站/机场或到达站/机场坐标，填写departure_coordinates/arrival_coordinates；同时estimated_cost应包含该交通费用。
- query_trains: 如果有出发城市且是国内行程，必须查询火车；如果采用某个车次进入行程，必须把车次号、出发/到达站、出发/到达时间和费用写入transport_detail。

如果工具调用失败，可以尝试其他工具或降级生成行程。"""
