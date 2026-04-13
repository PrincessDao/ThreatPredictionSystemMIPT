import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import incidents, stats, health
from app.middleware.logging import log_requests
from app.db.database import get_sync_client
from app.services.ml_analysis import ml_generator
from app.config import get_settings
from app.services.excel_loader import load_incidents_from_excel, load_threats_from_excel

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

settings = get_settings()

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

    cnt_incidents = client.query("SELECT count() FROM incidents").result_rows[0][0]
    if cnt_incidents == 0:
        logging.info("Loading incidents from Excel...")
        incidents_data = load_incidents_from_excel(settings.INCIDENTS_FILE_PATH)
        if incidents_data:
            data_tuples = [
                (
                    row["id"], row["timestamp"], row["regional_time"],
                    row["industry"], row["region"], row["hosts_count"],
                    row["threat_code"], row["success"], row["hour"],
                    row["day_of_week"], row["month"], row["season"],
                    row["created_at"]
                )
                for row in incidents_data
            ]
            client.insert(
                "incidents",
                data_tuples,
                columns=["id", "timestamp", "regional_time", "industry", "region",
                         "hosts_count", "threat_code", "success", "hour",
                         "day_of_week", "month", "season", "created_at"]
            )
            logging.info(f"Loaded {len(incidents_data)} incidents")
        else:
            logging.warning("No incidents found in Excel file")

    cnt_threats = client.query("SELECT count() FROM threats").result_rows[0][0]
    if cnt_threats == 0:
        logging.info("Loading threats from Excel...")
        threats_data = load_threats_from_excel(settings.THREATS_FILE_PATH)
        if threats_data:
            threats_tuples = [(t["Код_угрозы"], t["Название_угрозы"]) for t in threats_data]
            client.insert("threats", threats_tuples, columns=["code", "name"])
            logging.info(f"Loaded {len(threats_data)} threats")
        else:
            logging.warning("No threats found in Excel file")

    client.close()

@app.on_event("startup")
async def preload_ml_artifacts():
    ml_generator.load_artifacts()

@app.on_event("shutdown")
async def shutdown():
    from app.services.cache import cache
    await cache.close()