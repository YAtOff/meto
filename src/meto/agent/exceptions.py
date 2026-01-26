class AgentError(Exception):
    pass


class SubagentError(AgentError):
    pass


class MaxStepsExceededError(AgentError):
    pass


class ToolExecutionError(AgentError):
    pass


class ToolNotFoundError(AgentError):
    pass
