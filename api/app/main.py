from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.sessions import router as sessions_router
from app.config import cors_origins

app = FastAPI(
    title="MeaningSync API",
    description="Deterministic agreement-clarity workflow for MeaningSync.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(sessions_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
