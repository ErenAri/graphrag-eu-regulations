from fastapi import FastAPI

from app.api.routes.actions import router as actions_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.neo4j import close_driver
from app.db.schema import ensure_schema

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(actions_router)


@app.on_event("startup")
def startup() -> None:
    ensure_schema()


@app.on_event("shutdown")
def shutdown() -> None:
    close_driver()
