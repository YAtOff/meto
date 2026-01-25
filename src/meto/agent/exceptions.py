class AgentError(Exception):
    pass


class MaxStepsExceededError(AgentError):
    pass


class ToolExecutionError(AgentError):
    pass


class SubagentError(AgentError):
    pass
