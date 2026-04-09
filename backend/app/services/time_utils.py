from datetime import datetime

def compute_time_fields(regional_time: datetime):
    hour = regional_time.hour
    day_of_week = regional_time.weekday()
    month = regional_time.month
    if month in (12, 1, 2):
        season = "зима"
    elif month in (3, 4, 5):
        season = "весна"
    elif month in (6, 7, 8):
        season = "лето"
    else:
        season = "осень"
    return {
        "hour": hour,
        "day_of_week": day_of_week,
        "month": month,
        "season": season,
    }
