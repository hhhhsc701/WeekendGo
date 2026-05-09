from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.mcp.client import MCPClientManager
from app.mcp.config_loader import load_mcp_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a configured MCP server connection.")
    parser.add_argument("--config", default="config/mcp_config.yaml")
    parser.add_argument("--server", required=True)
    parser.add_argument("--tool")
    parser.add_argument("--region", choices=["domestic", "international"], default="domestic")
    parser.add_argument("--params-json", default="{}")
    return parser.parse_args()


async def verify(args: argparse.Namespace) -> dict[str, Any]:
    config = load_mcp_config(Path(args.config), enabled_servers={args.server})
    manager = MCPClientManager(config)
    await manager.initialize()
    try:
        if args.server not in manager.available_servers:
            raise RuntimeError(f"MCP server {args.server} did not initialize")

        result: dict[str, Any] = {
            "server": args.server,
            "availableServers": manager.available_servers,
            "tools": sorted(manager.tool_registry.get(args.server, set())),
        }
        if args.tool:
            params = json.loads(args.params_json)
            call_result = await manager.call(args.region, args.tool, params)
            result["call"] = {
                "tool": args.tool,
                "ok": True,
                "resultType": type(call_result).__name__,
            }
        return result
    finally:
        await manager.close()


def main() -> None:
    args = parse_args()
    print(json.dumps(asyncio.run(verify(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
