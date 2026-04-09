from fastapi import APIRouter, HTTPException
from app.services.cache import cache
from app.db.database import get_clickhouse_client
from app.db.queries import (
    get_total_incidents, get_successful_incidents,
    get_top_industries, get_top_regions,
    get_success_rate_by_hour, get_success_rate_by_dayofweek,
    get_success_rate_by_month, get_success_rate_by_season,
    get_top_threats_frequent, get_top_threats_successful,
    get_industry_stats, get_region_stats
)
from app.schemas.stats import SummaryStats, TemporalStats, ThreatStats, IndustryStats

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

@router.get("/summary", response_model=SummaryStats)
async def summary_stats():
    key = cache.make_key("summary")
    cached = await cache.get(key)
    if cached:
        return cached
    client = await get_clickhouse_client()
    try:
        total = await get_total_incidents(client)
        successful = await get_successful_incidents(client)
        success_rate = (successful / total * 100) if total > 0 else 0.0
        top_industries = await get_top_industries(client, 5)
        top_regions = await get_top_regions(client, 5)
        result = {
            "total_incidents": total,
            "successful_incidents": successful,
            "success_rate": round(success_rate, 2),
            "top_industries": top_industries,
            "top_regions": top_regions,
        }
    finally:
        await client.close()
    await cache.set(key, result)
    return result

@router.get("/temporal", response_model=TemporalStats)
async def temporal_stats():
    key = cache.make_key("temporal")
    cached = await cache.get(key)
    if cached:
        return cached
    client = await get_clickhouse_client()
    try:
        by_hour = await get_success_rate_by_hour(client)
        by_day = await get_success_rate_by_dayofweek(client)
        by_month = await get_success_rate_by_month(client)
        by_season = await get_success_rate_by_season(client)
        result = {
            "success_rate_by_hour": by_hour,
            "success_rate_by_dayofweek": by_day,
            "success_rate_by_month": by_month,
            "success_rate_by_season": by_season,
        }
    finally:
        await client.close()
    await cache.set(key, result)
    return result

@router.get("/top-threats", response_model=ThreatStats)
async def top_threats():
    key = cache.make_key("top_threats")
    cached = await cache.get(key)
    if cached:
        return cached
    client = await get_clickhouse_client()
    try:
        frequent = await get_top_threats_frequent(client, 10)
        successful = await get_top_threats_successful(client, 10, 10)
        result = {
            "most_frequent": frequent,
            "most_successful": successful,
        }
    finally:
        await client.close()
    await cache.set(key, result)
    return result

@router.get("/industry/{industry_name}", response_model=IndustryStats)
async def industry_stats(industry_name: str):
    key = cache.make_key(f"industry:{industry_name}")
    cached = await cache.get(key)
    if cached:
        return cached
    client = await get_clickhouse_client()
    try:
        stats = await get_industry_stats(client, industry_name)
        if stats is None:
            raise HTTPException(status_code=404, detail=f"Industry '{industry_name}' not found")
    finally:
        await client.close()
    await cache.set(key, stats)
    return stats

@router.get("/region/{region_name}")
async def region_stats(region_name: str):
    key = cache.make_key(f"region:{region_name}")
    cached = await cache.get(key)
    if cached:
        return cached
    client = await get_clickhouse_client()
    try:
        stats = await get_region_stats(client, region_name)
        if stats is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_name}' not found")
    finally:
        await client.close()
    await cache.set(key, stats)
    return stats
