import os
import sys
import django
import pandas as pd
import numpy as np

sys.path.append('/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from security_app.models import Incident, Threat


def load_incidents():
    qs = Incident.objects.all().values(
        'enterprise_type',
        'enterprise_code',
        'host_count',
        'threat_code',
        'success',
        'region',
        'incident_date',
        'incident_time'
    )

    df = pd.DataFrame(list(qs))

    df = df.rename(columns={
        'enterprise_type': 'Тип_предприятия',
        'enterprise_code': 'Код_предприятия',
        'host_count': 'Количество_хостов',
        'threat_code': 'Код_реализованной_угрозы',
        'success': 'Успех',
        'region': 'Регион_размещения_предприятия',
        'incident_date': 'Дата_инцидента',
        'incident_time': 'Региональное_время'
    })

    df['Тип_предприятия'] = df['Тип_предприятия'].astype('object')
    df['Регион_размещения_предприятия'] = df['Регион_размещения_предприятия'].astype('object')

    df['Код_предприятия'] = df['Код_предприятия'].astype('int64')
    df['Количество_хостов'] = df['Количество_хостов'].astype('int64')
    df['Код_реализованной_угрозы'] = df['Код_реализованной_угрозы'].astype('int64')
    df['Успех'] = df['Успех'].astype('int64')

    df['Региональное_время'] = pd.to_datetime(df['Региональное_время'], utc=True).dt.tz_localize(None)
    df['Дата_инцидента'] = pd.to_datetime(df['Дата_инцидента'], utc=True).dt.tz_localize(None)

    df['час'] = df['Региональное_время'].dt.hour.astype('int32')
    df['день_недели'] = df['Региональное_время'].dt.dayofweek.astype('int32')
    df['месяц'] = df['Региональное_время'].dt.month.astype('int32')

    def get_season(m):
        if m in [12, 1, 2]:
            return 'зима'
        elif m in [3, 4, 5]:
            return 'весна'
        elif m in [6, 7, 8]:
            return 'лето'
        return 'осень'

    df['сезон'] = df['месяц'].apply(get_season)

    return df


def load_threats():
    qs = Threat.objects.all().values('threat_id', 'name')
    df = pd.DataFrame(list(qs))

    df = df.rename(columns={
        'threat_id': 'Идентификатор УБИ',
        'name': 'Наименование УБИ'
    })

    df['Идентификатор_целое'] = (
        df['Идентификатор УБИ']
        .astype(str)
        .str.split('.')
        .str[0]
        .astype('int32')
    )

    df = df.rename(columns={
        'Идентификатор_целое': 'Код_угрозы',
        'Наименование УБИ': 'Название_угрозы'
    })

    return df[['Код_угрозы', 'Название_угрозы']]


def merge_data(incidents, threats):
    return incidents.merge(
        threats,
        left_on='Код_реализованной_угрозы',
        right_on='Код_угрозы',
        how='left'
    )


if __name__ == "__main__":
    incidents = load_incidents()
    threats = load_threats()
    df = merge_data(incidents, threats)