class MCPError(RuntimeError):
    pass


class MCPConfigurationError(MCPError):
    pass


class MCPToolError(MCPError):
    pass


class MCPTimeoutError(MCPError):
    pass