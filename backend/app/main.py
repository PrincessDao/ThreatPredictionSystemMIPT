import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import incidents, stats, health
from app.middleware.logging import log_requests
from app.db.database import get_sync_client
from app.services.ml_analysis import ml_generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Analytics Backend for InfoSec", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(log_requests)

app.include_router(incidents.router)
app.include_router(stats.router)
app.include_router(health.router)

@app.on_event("startup")
async def init_db():
    client = get_sync_client()
    client.command("""
        CREATE TABLE IF NOT EXISTS incidents (
            id UUID,
            timestamp DateTime,
            regional_time DateTime,
            industry String,
            region String,
            hosts_count UInt32,
            threat_code UInt16,
            success UInt8,
            hour UInt8,
            day_of_week UInt8,
            month UInt8,
            season String,
            created_at DateTime
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, industry)
    """)
    client.command("""
        CREATE TABLE IF NOT EXISTS threats (
            code UInt16,
            name String
        ) ENGINE = TinyLog
    """)
    cnt = client.query("SELECT count() FROM threats").result_rows[0][0]
    if cnt == 0:
        threats_data = [
            (1, "Утечка данных"),
            (2, "DDoS-атака"),
            (3, "Фишинг"),
            (4, "Вредоносное ПО"),
            (5, "Социальная инженерия"),
            (6, "Атака на веб-приложение"),
            (7, "Скомпрометированные учётные данные"),
            (8, "Отказ в обслуживании"),
            (9, "Внутренняя угроза"),
            (10, "Атака через периферийные устройства"),
            (11, "Ransomware"),
            (12, "Man-in-the-Middle"),
        ]
        client.insert("threats", threats_data, columns=["code", "name"])
    client.close()

@app.on_event("startup")
async def preload_ml_artifacts():
    ml_generator.load_artifacts()

@app.on_event("shutdown")
async def shutdown():
    from app.services.cache import cache
    await cache.close()