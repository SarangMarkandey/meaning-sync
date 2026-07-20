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
    openai_transcription_model: str = "gpt-realtime-whisper"
    meaningsync_audio_consent_notice_version: str = "audio-transcription-v1"
    meaningsync_audio_max_turn_seconds: int = Field(default=60, ge=5, le=3600)
    meaningsync_audio_max_session_seconds_per_participant: int = Field(
        default=600, ge=5, le=86400
    )
    meaningsync_realtime_initialization_timeout_seconds: float = Field(
        default=12, gt=0, le=120
    )
    meaningsync_audio_idle_timeout_seconds: int = Field(default=20, ge=5, le=600)
    meaningsync_audio_max_transcript_length: int = Field(default=2000, ge=2, le=20000)
    meaningsync_audio_max_concurrent_sessions_per_participant: int = Field(
        default=1, ge=1, le=5
    )
    meaningsync_clarification_attempt_limit: int = Field(default=3, ge=1, le=10)
    meaningsync_database_url: str = "sqlite:///./meaningsync-local.db"
    meaningsync_session_ttl_hours: int = Field(default=24, ge=1, le=720)
    meaningsync_access_token_ttl_hours: int = Field(default=24, ge=1, le=720)
    meaningsync_invite_ttl_minutes: int = Field(default=15, ge=1, le=1440)

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
