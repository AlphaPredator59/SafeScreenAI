"""Schemas for service health checks."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public response returned by the health endpoint."""

    status: str
    service: str
