from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.agent.errors import AgentError, AgentTimeoutError, AgentOutputError
from app.mcp.errors import MCPError, MCPConfigurationError, MCPToolError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AgentTimeoutError)
    async def agent_timeout_handler(_: Request, exc: AgentTimeoutError) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    @app.exception_handler(AgentOutputError)
    async def agent_output_handler(_: Request, exc: AgentOutputError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(AgentError)
    async def agent_error_handler(_: Request, exc: AgentError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(MCPConfigurationError)
    async def mcp_config_handler(_: Request, exc: MCPConfigurationError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(MCPToolError)
    async def mcp_tool_handler(_: Request, exc: MCPToolError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(MCPError)
    async def mcp_error_handler(_: Request, exc: MCPError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})