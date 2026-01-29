"""Custom exception types used across the agent runtime."""


class AgentError(Exception):
    """Base class for meto agent errors."""


class SubagentError(AgentError):
    """Raised when a subagent cannot be created or executed."""


class MaxStepsExceededError(AgentError):
    """Raised when the agent loop exceeds its configured turn budget."""


class ToolExecutionError(AgentError):
    """Raised when a tool fails to execute (tool runner layer)."""


class ToolNotFoundError(AgentError):
    """Raised when an unknown tool name is requested."""


class AgentInterrupted(AgentError):
    """Raised when the agent loop is interrupted by user (Ctrl-C)."""
