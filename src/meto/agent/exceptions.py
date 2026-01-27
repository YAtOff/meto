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


class AgentInterrupted(AgentError):
    """Raised when the agent loop is interrupted by user (Ctrl-C)."""

    pass
