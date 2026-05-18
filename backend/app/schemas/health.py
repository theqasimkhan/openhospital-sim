from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    app: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: dict[str, ServiceStatus] = Field(default_factory=dict)

    model_config = {"json_schema_extra": {
        "example": {
            "status": "ok",
            "app": "OpenHospital Sim",
            "version": "0.1.0",
            "environment": "development",
            "timestamp": "2026-05-18T00:00:00Z",
            "services": {
                "postgres": {"status": "ok", "latency_ms": 1.2},
                "redis": {"status": "ok", "latency_ms": 0.4},
            },
        }
    }}


class PingResponse(BaseModel):
    ping: Literal["pong"] = "pong"
