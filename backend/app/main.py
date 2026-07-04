"""FastAPI app entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, sse, v1
from app.config import settings

app = FastAPI(title="Compliance — Agent Console", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1.router, prefix="/api/v1", tags=["v1"])
app.include_router(sse.router, prefix="/api/v1", tags=["sse"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])


@app.get("/")
def root() -> dict:
    return {"service": "compliance", "data_source": settings.data_source,
            "storage": settings.storage, "review_date": str(settings.review_date)}
