import pandas as pd
import uuid
from datetime import datetime
from app.services.time_utils import compute_time_fields

def load_incidents_from_excel(file_path: str):
    df = pd.read_excel(file_path, sheet_name='Sheet1')
    df.columns = df.columns.str.strip().str.replace(' ', '_')
    df['Региональное_время'] = pd.to_datetime(df['Региональное_время'], dayfirst=True)
    rows = []
    now_utc = datetime.utcnow()
    for _, row in df.iterrows():
        regional_time = row['Региональное_время']
        time_fields = compute_time_fields(regional_time)
        rows.append({
            "id": str(uuid.uuid4()),
            "timestamp": now_utc,
            "regional_time": regional_time,
            "industry": row['Тип_предприятия'],
            "region": row['Регион_размещения_предприятия'],
            "hosts_count": int(row['Количество_хостов']),
            "threat_code": int(row['Код_реализованной_угрозы']),
            "success": int(row['Успех']),
            "hour": time_fields["hour"],
            "day_of_week": time_fields["day_of_week"],
            "month": time_fields["month"],
            "season": time_fields["season"],
            "created_at": now_utc
        })
    return rows

def load_threats_from_excel(file_path: str):
    df = pd.read_excel(file_path, sheet_name='Sheet', header=1)
    df = df[['Идентификатор УБИ', 'Наименование УБИ']].copy()
    df = df.dropna(subset=['Идентификатор УБИ'])
    df['Идентификатор_целое'] = df['Идентификатор УБИ'].astype(str).str.split('.').str[0].astype(int)
    df = df.rename(columns={'Идентификатор_целое': 'Код_угрозы', 'Наименование УБИ': 'Название_угрозы'})
    threats = df[['Код_угрозы', 'Название_угрозы']].drop_duplicates(subset=['Код_угрозы']).to_dict('records')
    return threats