from __future__ import annotations

import re
from typing import Literal

Region = Literal["domestic", "international"]

CHINESE_CITIES = {
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "成都",
    "武汉",
    "西安",
    "南京",
    "苏州",
    "重庆",
    "天津",
    "长沙",
    "青岛",
    "厦门",
    "昆明",
    "大连",
    "三亚",
    "桂林",
    "丽江",
    "宁波",
    "无锡",
    "福州",
    "济南",
    "郑州",
    "合肥",
    "哈尔滨",
    "沈阳",
    "长春",
    "石家庄",
    "太原",
    "南昌",
    "南宁",
    "贵阳",
    "海口",
    "拉萨",
    "乌鲁木齐",
    "呼和浩特",
    "香港",
    "澳门",
    "台北",
}

CHINESE_CITY_ALIASES = {
    "beijing",
    "peking",
    "shanghai",
    "guangzhou",
    "canton",
    "shenzhen",
    "hangzhou",
    "chengdu",
    "wuhan",
    "xian",
    "xi'an",
    "nanjing",
    "suzhou",
    "chongqing",
    "tianjin",
    "changsha",
    "qingdao",
    "xiamen",
    "kunming",
    "dalian",
    "sanya",
    "guilin",
    "lijiang",
    "ningbo",
    "wuxi",
    "fuzhou",
    "jinan",
    "zhengzhou",
    "hefei",
    "harbin",
    "shenyang",
    "changchun",
    "shijiazhuang",
    "taiyuan",
    "nanchang",
    "nanning",
    "guiyang",
    "haikou",
    "lhasa",
    "urumqi",
    "wulumuqi",
    "hohhot",
    "hong kong",
    "hongkong",
    "macau",
    "macao",
    "taipei",
}

CHINESE_CITY_COORDINATES = {
    "北京": (39.9042, 116.4074),
    "beijing": (39.9042, 116.4074),
    "peking": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "shanghai": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "guangzhou": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "shenzhen": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "hangzhou": (30.2741, 120.1551),
    "成都": (30.5728, 104.0668),
    "chengdu": (30.5728, 104.0668),
    "香港": (22.3193, 114.1694),
    "hong kong": (22.3193, 114.1694),
    "hongkong": (22.3193, 114.1694),
    "澳门": (22.1987, 113.5439),
    "macau": (22.1987, 113.5439),
    "macao": (22.1987, 113.5439),
}

INTERNATIONAL_CITY_ALIASES = {
    "tokyo",
    "paris",
    "new york",
    "london",
    "seoul",
    "singapore",
    "bangkok",
    "osaka",
    "kyoto",
    "rome",
    "berlin",
    "sydney",
    "melbourne",
    "los angeles",
    "san francisco",
}


def contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def normalize_city_name(city_name: str) -> str:
    normalized = city_name.strip().removesuffix("市").removesuffix(" City").removesuffix(" city")
    return re.sub(r"\s+", " ", normalized)


def is_chinese_city(city_name: str) -> bool:
    normalized = normalize_city_name(city_name)
    if normalized in CHINESE_CITIES:
        return True
    normalized_lower = normalized.lower()
    if normalized_lower in CHINESE_CITY_ALIASES:
        return True
    if normalized_lower in INTERNATIONAL_CITY_ALIASES:
        return False
    return contains_chinese(normalized)


class RegionRouter:
    def region_for_city(self, city_name: str) -> Region:
        return "domestic" if is_chinese_city(city_name) else "international"

    def server_candidates(
        self,
        region: Region,
        tool_name: str,
        routes: dict,
        servers: dict,
    ) -> list[str]:
        route = routes[region]
        ordered = [route.primary, *route.shared]
        return [
            server_name
            for server_name in ordered
            if server_name in servers
            and servers[server_name].enabled
            and tool_name in servers[server_name].tools
        ]


def fallback_chinese_city_coordinates(city_name: str) -> tuple[float, float] | None:
    normalized = normalize_city_name(city_name)
    return CHINESE_CITY_COORDINATES.get(normalized) or CHINESE_CITY_COORDINATES.get(normalized.lower())
