from fastapi import APIRouter, BackgroundTasks
from app.schemas.incident import IncidentBatch
from app.db.database import get_clickhouse_client
from app.services.time_utils import compute_time_fields
from app.db.queries import insert_incidents
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1", tags=["incidents"])

async def store_incidents_batch(events_data):
    client = await get_clickhouse_client()
    try:
        await insert_incidents(client, events_data)
    finally:
        await client.close()

@router.post("/incidents", status_code=202)
async def receive_incidents(batch: IncidentBatch, background_tasks: BackgroundTasks):
    events_data = []
    now_utc = datetime.utcnow()
    for event in batch.events:
        time_fields = compute_time_fields(event.regional_time)
        events_data.append({
            "id": str(uuid.uuid4()),
            "timestamp": now_utc,
            "regional_time": event.regional_time,
            "industry": event.industry,
            "region": event.region,
            "hosts_count": event.hosts_count,
            "threat_code": event.threat_code,
            "success": event.success,
            "hour": time_fields["hour"],
            "day_of_week": time_fields["day_of_week"],
            "month": time_fields["month"],
            "season": time_fields["season"],
            "created_at": now_utc,
        })
    background_tasks.add_task(store_incidents_batch, events_data)
    return {"status": "accepted", "received": len(events_data)}
