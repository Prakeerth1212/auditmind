
from fastapi import APIRouter
from auditmind.db.session import engine

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "auditmind"}


@router.get("/health/db")
async def health_db():
    """Checks DB connectivity — used by Docker healthcheck."""
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}