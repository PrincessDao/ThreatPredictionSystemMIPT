from pydantic import BaseModel
from typing import List, Dict, Any

class SummaryStats(BaseModel):
    total_incidents: int
    successful_incidents: int
    success_rate: float
    top_industries: List[Dict[str, Any]]
    top_regions: List[Dict[str, Any]]

class TemporalStats(BaseModel):
    success_rate_by_hour: List[Dict[str, float]]
    success_rate_by_dayofweek: List[Dict[str, float]]
    success_rate_by_month: List[Dict[str, float]]
    success_rate_by_season: List[Dict[str, float]]

class ThreatStats(BaseModel):
    most_frequent: List[Dict[str, Any]]
    most_successful: List[Dict[str, Any]]

class IndustryStats(BaseModel):
    total_incidents: int
    success_rate: float
    top_regions_in_industry: List[Dict[str, Any]]
    temporal_patterns: TemporalStats
