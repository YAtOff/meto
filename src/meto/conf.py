"""Configuration management for LazyFS using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings configurable via environment variables and .env file.

    Environment variables must be prefixed with METO_.
    Example: METO_LLM_API_KEY=your_api_key
    """

    model_config = SettingsConfigDict(  # pyright: ignore[reportUnannotatedClassAttribute]
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="METO_",
        case_sensitive=False,
        extra="ignore",
    )

    LLM_API_KEY: str = Field(
        default="sk-<litellm-proxy-or-virtual-key>",
        description="API key for LiteLLM proxy",
    )

    LLM_BASE_URL: str = Field(
        default="http://localhost:4444",
        description="Base URL for LiteLLM proxy",
    )

    DEFAULT_MODEL: str = Field(
        default="gpt-4.1",
        description="Default model name to use with LiteLLM",
    )

    # --- Agent loop tuning ---

    MAX_TURNS: int = Field(
        default=25,
        description="Maximum number of model/tool iterations per prompt.",
    )

    TOOL_TIMEOUT_SECONDS: int = Field(
        default=300,
        description="Timeout (seconds) for a single shell tool command execution.",
    )

    MAX_TOOL_OUTPUT_CHARS: int = Field(
        default=50000,
        description="Maximum number of characters captured from a tool result.",
    )

    ECHO_COMMANDS: bool = Field(
        default=True,
        description="Whether to print executed shell commands and their outputs.",
    )

    MAX_ECHO_CHARS: int = Field(
        default=256,
        description="Maximum number of characters to print when echoing commands and outputs.",
    )


# Global settings instance
settings = Settings()
