"""Configuration via pydantic-settings."""

from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings

# Input size limits
MAX_XML_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PDF_BASE64_SIZE = 67 * 1024 * 1024  # ~50 MB decoded (base64 overhead ~33%)


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    kosit_url: str = "http://localhost:8081"
    mcp_port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("kosit_url")
    @classmethod
    def validate_kosit_url(cls, v: str) -> str:
        AnyHttpUrl(v)
        return v


settings = Settings()
