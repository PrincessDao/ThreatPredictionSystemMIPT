from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = ""
    CLICKHOUSE_DB: str = "default"
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
