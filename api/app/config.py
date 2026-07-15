import os

def cors_origins() -> list[str]:
    raw_origins = os.getenv(
        "MEANINGSYNC_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",")]
    explicit_origins = [origin for origin in origins if origin]
    if not explicit_origins or "*" in explicit_origins:
        raise ValueError("MEANINGSYNC_CORS_ORIGINS must list explicit origins")
    return explicit_origins
