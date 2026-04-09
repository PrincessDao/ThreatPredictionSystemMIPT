from fastapi import APIRouter
from app.services.cache import cache
from app.db.database import get_clickhouse_client

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    try:
        await cache.redis.ping()
    except Exception:
        return {"status": "redis_unavailable"}, 503
    try:
        client = await get_clickhouse_client()
        await client.query("SELECT 1")
        await client.close()
    except Exception:
        return {"status": "clickhouse_unavailable"}, 503
    return {"status": "ok"}
