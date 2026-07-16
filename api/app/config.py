from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    meaningsync_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6"
    openai_store_responses: bool = False
    openai_request_timeout_seconds: float = Field(default=30, gt=0, le=120)
    meaningsync_clarification_attempt_limit: int = Field(default=3, ge=1, le=10)

    @field_validator("openai_store_responses")
    @classmethod
    def responses_must_not_be_stored(cls, value: bool) -> bool:
        if value:
            raise ValueError("OPENAI_STORE_RESPONSES must remain false")
        return value

    @property
    def cors_origins(self) -> list[str]:
        origins = [
            origin.strip().rstrip("/")
            for origin in self.meaningsync_cors_origins.split(",")
        ]
        explicit_origins = [origin for origin in origins if origin]
        if not explicit_origins or "*" in explicit_origins:
            raise ValueError("MEANINGSYNC_CORS_ORIGINS must list explicit origins")
        return explicit_origins


def get_settings() -> Settings:
    return Settings()


def cors_origins() -> list[str]:
    return get_settings().cors_origins
