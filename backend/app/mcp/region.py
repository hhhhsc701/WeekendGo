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
    return city_name.strip().removesuffix("市").removesuffix(" City")


def is_chinese_city(city_name: str) -> bool:
    normalized = normalize_city_name(city_name)
    if normalized in CHINESE_CITIES:
        return True
    if normalized.lower() in INTERNATIONAL_CITY_ALIASES:
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
