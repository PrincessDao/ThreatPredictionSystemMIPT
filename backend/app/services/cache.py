import json
import hashlib
from redis.asyncio import Redis
from app.config import get_settings

settings = get_settings()

class RedisCache:
    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get(self, key: str):
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value, ttl: int = None):
        if ttl is None:
            ttl = settings.CACHE_TTL
        await self.redis.setex(key, ttl, json.dumps(value))

    async def close(self):
        await self.redis.close()

    @staticmethod
    def make_key(prefix: str, params: dict = None):
        if not params:
            return f"cache:{prefix}"
        sorted_params = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        hashed = hashlib.md5(param_str.encode()).hexdigest()
        return f"cache:{prefix}:{hashed}"

cache = RedisCache()
