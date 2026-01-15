from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.neo4j import check_ready

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> JSONResponse:
    if check_ready():
        return JSONResponse(content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "not_ready"})
