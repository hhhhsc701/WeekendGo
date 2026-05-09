from __future__ import annotations

from typing import Any


TRIP_GENERATION_SYSTEM_PROMPT = """你是 WeekendGo 的行程规划助手。
你必须只输出 JSON，不要输出 Markdown 或解释文字。行程需要真实、紧凑、可执行，并考虑天气、路线、预算和同行人群。
如果外部数据不足，可以合理降级，但必须在 notes 字段说明数据限制。"""


TRIP_REFINEMENT_SYSTEM_PROMPT = """你是 WeekendGo 的行程调整助手。
你必须只输出 JSON，不要输出 Markdown 或解释文字。先解析用户调整意图，再输出调整后的完整行程或需要澄清的问题。"""


def build_trip_generation_prompt(context: dict[str, Any]) -> str:
    return f"""请基于以下 JSON 上下文生成周末行程：

{context}

输出必须包含：
- title
- input
- region
- weather_summary
- transportation
- total_budget
- items
- notes
"""


def build_refinement_prompt(original_trip: dict[str, Any], request_text: str) -> str:
    return f"""原行程 JSON：
{original_trip}

用户调整请求：
{request_text}

请输出 JSON，包含：
- intent
- needs_clarification
- clarification_question
- updated_trip
- conflicts
"""
