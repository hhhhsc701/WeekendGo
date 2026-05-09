from dataclasses import dataclass


class MCPConfigurationError(RuntimeError):
    """Raised when MCP configuration cannot be loaded or resolved."""


class MCPToolError(RuntimeError):
    """Raised when an MCP tool call fails in a controlled way."""


class MCPToolTimeoutError(MCPToolError):
    """Raised when an MCP tool call exceeds the configured timeout."""


@dataclass(frozen=True)
class MCPErrorEnvelope:
    code: str
    message: str
    server: str | None = None
    tool: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "server": self.server,
            "tool": self.tool,
        }


def wrap_tool_error(
    exc: BaseException,
    *,
    server: str | None = None,
    tool: str | None = None,
) -> MCPErrorEnvelope:
    if isinstance(exc, MCPToolTimeoutError):
        code = "tool_timeout"
    elif isinstance(exc, MCPConfigurationError):
        code = "configuration_error"
    else:
        code = "tool_error"
    return MCPErrorEnvelope(code=code, message=str(exc), server=server, tool=tool)
