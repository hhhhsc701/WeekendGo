class AgentError(RuntimeError):
    pass


class AgentOutputError(AgentError):
    pass


class AgentTimeoutError(AgentError):
    pass