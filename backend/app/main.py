"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_application() -> FastAPI:
    """Create and configure the SafeScreen AI API application."""
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(title=settings.app_name)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_application()
