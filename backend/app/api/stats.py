from fastapi import APIRouter, HTTPException
from app.services.cache import cache
from app.db.database import get_clickhouse_client
from app.db.queries import (
    get_total_incidents, get_successful_incidents,
    get_top_industries, get_top_regions,
    get_success_rate_by_hour, get_success_rate_by_dayofweek,
    get_success_rate_by_month, get_success_rate_by_season,
    get_top_threats_frequent, get_top_threats_successful,
    get_industry_stats, get_region_stats,
    get_hour_max_success_rate,
    get_day_of_week_max_success_rate,
    get_month_max_success_rate,
    get_top_industries_by_incidents,
    get_top_regions_by_incidents,
    get_top_threats_by_success_rate,
    get_overall_success_rate,
    get_industry_success_rate,
    get_region_success_rate,
)
from app.schemas.stats import SummaryStats, TemporalStats, ThreatStats, IndustryStats
from app.services.ml_analysis import ml_generator

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

@router.get("/recommendations")
async def get_recommendations():
    key = cache.make_key("recommendations")
    cached = await cache.get(key)
    if cached:
        return cached
    client = await get_clickhouse_client()
    try:
        hour, hour_rate = await get_hour_max_success_rate(client)
        dow, dow_rate = await get_day_of_week_max_success_rate(client)
        month, month_rate = await get_month_max_success_rate(client)
        top_industries = await get_top_industries_by_incidents(client, 3)
        top_regions = await get_top_regions_by_incidents(client, 3)
        top_threats = await get_top_threats_by_success_rate(client, min_incidents=5, limit=5)
        overall_rate = await get_overall_success_rate(client)
        high_risk_industries = []
        for ind in top_industries:
            ind_rate = await get_industry_success_rate(client, ind)
            if ind_rate > overall_rate:
                high_risk_industries.append(ind)
        high_risk_regions = []
        for reg in top_regions:
            reg_rate = await get_region_success_rate(client, reg)
            if reg_rate > overall_rate:
                high_risk_regions.append(reg)
        recommendations_text = []
        recommendations_text.append("=== Рекомендации по усилению защиты ===")
        if hour is not None:
            recommendations_text.append(f"1. Временная защита: усилить мониторинг в {hour}:00, по {dow}-му дню недели и в {month}-м месяце.")
        else:
            recommendations_text.append("1. Недостаточно данных для временных рекомендаций.")
        if top_industries:
            recommendations_text.append(f"2. Отраслевая защита: особое внимание уделить отраслям {top_industries}.")
        else:
            recommendations_text.append("2. Нет данных по отраслям.")
        if top_regions:
            recommendations_text.append(f"3. Региональная защита: повышенный контроль в регионах {top_regions}.")
        else:
            recommendations_text.append("3. Нет данных по регионам.")
        if top_threats:
            recommendations_text.append(f"4. По угрозам: сконцентрироваться на предотвращении следующих типов атак: {top_threats}.")
        else:
            recommendations_text.append("4. Недостаточно данных по угрозам.")
        if high_risk_industries or high_risk_regions:
            factors = {}
            if high_risk_industries:
                factors["отрасли"] = high_risk_industries
            if high_risk_regions:
                factors["регионы"] = high_risk_regions
            recommendations_text.append(f"5. Ключевые факторы успешной атаки: {factors} (успешность выше среднего).")
            recommendations_text.append("   Рекомендуется усилить контроль по этим направлениям.")
        else:
            recommendations_text.append("5. Нет явных ключевых факторов выше среднего.")
        recommendations_text.append("\n6. Архитектура безопасности: использовать агрегированные данные для динамической корректировки политик безопасности.")
        result = {
            "recommendations": "\n".join(recommendations_text),
            "structured": {
                "temporal": {"hour": hour, "day_of_week": dow, "month": month},
                "top_industries": top_industries,
                "top_regions": top_regions,
                "top_threats_by_success": top_threats,
                "high_risk_factors": {"industries": high_risk_industries, "regions": high_risk_regions}
            }
        }
    finally:
        await client.close()
    await cache.set(key, result)
    return result

@router.get("/ml-report-enhanced")
async def get_ml_report_enhanced(force_refresh: bool = False):
    cache_key = "ml_report_enhanced"
    if not force_refresh:
        cached = await cache.get(cache_key)
        if cached:
            return cached
    report = ml_generator.generate_full_report(force_retrain=force_refresh)
    if "error" in report:
        raise HTTPException(status_code=503, detail=report["error"])
    await cache.set(cache_key, report, ttl=3600)
    return report

@router.get("/cluster-analysis")
async def get_cluster_analysis():
    key = cache.make_key("cluster_analysis")
    cached = await cache.get(key)
    if cached:
        return cached
    report = ml_generator.generate_full_report(force_retrain=False)
    if "error" in report:
        raise HTTPException(status_code=503, detail=report["error"])
    result = report.get("cluster_analysis")
    await cache.set(key, result, ttl=3600)
    return result

@router.get("/model-comparison")
async def get_model_comparison():
    key = cache.make_key("model_comparison")
    cached = await cache.get(key)
    if cached:
        return cached
    report = ml_generator.generate_full_report(force_retrain=False)
    if "error" in report:
        raise HTTPException(status_code=503, detail=report["error"])
    result = {
        "baseline_accuracy": report.get("baseline_accuracy"),
        "improved_accuracy": report.get("improved_accuracy"),
        "improvement": report.get("accuracy_improvement")
    }
    await cache.set(key, result, ttl=3600)
    return result