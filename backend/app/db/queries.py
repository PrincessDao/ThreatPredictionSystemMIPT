from typing import List, Dict, Any

async def execute_query(client, query: str, params: tuple = None) -> List[tuple]:
    result = await client.query(query, params=params)
    return result.result_rows

async def insert_incidents(client, rows: List[Dict]):
    data = [
        (
            row["id"], row["timestamp"], row["regional_time"],
            row["industry"], row["region"], row["hosts_count"],
            row["threat_code"], row["success"], row["hour"],
            row["day_of_week"], row["month"], row["season"],
            row["created_at"]
        )
        for row in rows
    ]
    await client.insert(
        "incidents",
        data,
        columns=["id", "timestamp", "regional_time", "industry", "region",
                 "hosts_count", "threat_code", "success", "hour",
                 "day_of_week", "month", "season", "created_at"]
    )

async def get_total_incidents(client) -> int:
    rows = await execute_query(client, "SELECT count() FROM incidents")
    return rows[0][0]

async def get_successful_incidents(client) -> int:
    rows = await execute_query(client, "SELECT count() FROM incidents WHERE success = 1")
    return rows[0][0]

async def get_top_industries(client, limit: int = 5) -> List[Dict]:
    rows = await execute_query(client, """
        SELECT industry, count() as cnt
        FROM incidents
        GROUP BY industry
        ORDER BY cnt DESC
        LIMIT %s
    """, (limit,))
    return [{"industry": r[0], "count": r[1]} for r in rows]

async def get_top_regions(client, limit: int = 5) -> List[Dict]:
    rows = await execute_query(client, """
        SELECT region, count() as cnt
        FROM incidents
        GROUP BY region
        ORDER BY cnt DESC
        LIMIT %s
    """, (limit,))
    return [{"region": r[0], "count": r[1]} for r in rows]

async def get_success_rate_by_hour(client, industry: str = None, region: str = None) -> List[Dict]:
    where = ""
    params = []
    if industry:
        where = "WHERE industry = %s"
        params.append(industry)
    elif region:
        where = "WHERE region = %s"
        params.append(region)
    query = f"""
        SELECT hour, avg(success) as rate
        FROM incidents
        {where}
        GROUP BY hour
        ORDER BY hour
    """
    rows = await execute_query(client, query, tuple(params))
    return [{"hour": r[0], "rate": round(r[1], 4)} for r in rows]

async def get_success_rate_by_dayofweek(client, industry: str = None, region: str = None) -> List[Dict]:
    where = ""
    params = []
    if industry:
        where = "WHERE industry = %s"
        params.append(industry)
    elif region:
        where = "WHERE region = %s"
        params.append(region)
    query = f"""
        SELECT day_of_week, avg(success) as rate
        FROM incidents
        {where}
        GROUP BY day_of_week
        ORDER BY day_of_week
    """
    rows = await execute_query(client, query, tuple(params))
    return [{"day_of_week": r[0], "rate": round(r[1], 4)} for r in rows]

async def get_success_rate_by_month(client, industry: str = None, region: str = None) -> List[Dict]:
    where = ""
    params = []
    if industry:
        where = "WHERE industry = %s"
        params.append(industry)
    elif region:
        where = "WHERE region = %s"
        params.append(region)
    query = f"""
        SELECT month, avg(success) as rate
        FROM incidents
        {where}
        GROUP BY month
        ORDER BY month
    """
    rows = await execute_query(client, query, tuple(params))
    return [{"month": r[0], "rate": round(r[1], 4)} for r in rows]

async def get_success_rate_by_season(client, industry: str = None, region: str = None) -> List[Dict]:
    where = ""
    params = []
    if industry:
        where = "WHERE industry = %s"
        params.append(industry)
    elif region:
        where = "WHERE region = %s"
        params.append(region)
    query = f"""
        SELECT season, avg(success) as rate
        FROM incidents
        {where}
        GROUP BY season
        ORDER BY rate DESC
    """
    rows = await execute_query(client, query, tuple(params))
    return [{"season": r[0], "rate": round(r[1], 4)} for r in rows]

async def get_top_threats_frequent(client, limit: int = 10) -> List[Dict]:
    rows = await execute_query(client, """
        SELECT i.threat_code, t.name, count() as cnt
        FROM incidents i
        LEFT JOIN threats t ON i.threat_code = t.code
        GROUP BY i.threat_code, t.name
        ORDER BY cnt DESC
        LIMIT %s
    """, (limit,))
    return [{"threat_code": r[0], "threat_name": r[1] or "Unknown", "count": r[2]} for r in rows]

async def get_top_threats_successful(client, limit: int = 10, min_count: int = 10) -> List[Dict]:
    rows = await execute_query(client, """
        SELECT i.threat_code, t.name, avg(success) as success_rate, count() as cnt
        FROM incidents i
        LEFT JOIN threats t ON i.threat_code = t.code
        GROUP BY i.threat_code, t.name
        HAVING cnt >= %s
        ORDER BY success_rate DESC
        LIMIT %s
    """, (min_count, limit))
    return [{"threat_code": r[0], "threat_name": r[1] or "Unknown", "success_rate": round(r[2], 4)} for r in rows]

async def get_industry_stats(client, industry: str):
    rows_total = await execute_query(client, "SELECT count() FROM incidents WHERE industry = %s", (industry,))
    total = rows_total[0][0]
    if total == 0:
        return None
    rows_rate = await execute_query(client, "SELECT avg(success) FROM incidents WHERE industry = %s", (industry,))
    rate = round(rows_rate[0][0], 4)
    rows_regions = await execute_query(client, """
        SELECT region, count() as cnt
        FROM incidents
        WHERE industry = %s
        GROUP BY region
        ORDER BY cnt DESC
        LIMIT 3
    """, (industry,))
    top_regions = [{"region": r[0], "count": r[1]} for r in rows_regions]
    temporal = {
        "success_rate_by_hour": await get_success_rate_by_hour(client, industry=industry),
        "success_rate_by_dayofweek": await get_success_rate_by_dayofweek(client, industry=industry),
        "success_rate_by_month": await get_success_rate_by_month(client, industry=industry),
        "success_rate_by_season": await get_success_rate_by_season(client, industry=industry),
    }
    return {"total_incidents": total, "success_rate": rate, "top_regions_in_industry": top_regions, "temporal_patterns": temporal}

async def get_region_stats(client, region: str):
    rows_total = await execute_query(client, "SELECT count() FROM incidents WHERE region = %s", (region,))
    total = rows_total[0][0]
    if total == 0:
        return None
    rows_rate = await execute_query(client, "SELECT avg(success) FROM incidents WHERE region = %s", (region,))
    rate = round(rows_rate[0][0], 4)
    rows_industries = await execute_query(client, """
        SELECT industry, count() as cnt
        FROM incidents
        WHERE region = %s
        GROUP BY industry
        ORDER BY cnt DESC
        LIMIT 3
    """, (region,))
    top_industries = [{"industry": r[0], "count": r[1]} for r in rows_industries]
    temporal = {
        "success_rate_by_hour": await get_success_rate_by_hour(client, region=region),
        "success_rate_by_dayofweek": await get_success_rate_by_dayofweek(client, region=region),
        "success_rate_by_month": await get_success_rate_by_month(client, region=region),
        "success_rate_by_season": await get_success_rate_by_season(client, region=region),
    }
    return {"total_incidents": total, "success_rate": rate, "top_industries_in_region": top_industries, "temporal_patterns": temporal}
