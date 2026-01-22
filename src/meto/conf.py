"""Configuration management for LazyFS using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings configurable via environment variables and .env file.

    Environment variables must be prefixed with METO_.
    Example: METO_LITELLM_API_KEY=your_api_key
    """

    model_config = SettingsConfigDict(  # pyright: ignore[reportUnannotatedClassAttribute]
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="METO_",
        case_sensitive=False,
    )

    LITELLM_API_KEY: str = Field(
        default="sk-<litellm-proxy-or-virtual-key>",
        description="API key for LiteLLM proxy",
    )

    LITELLM_BASE_URL: str = Field(
        default="http://localhost:4444",
        description="Base URL for LiteLLM proxy",
    )

    DEFAULT_MODEL: str = Field(
        default="gpt-4.1",
        description="Default model name to use with LiteLLM",
    )


# Global settings instance
settings = Settings()
