# security_app/management/commands/load_data.py
from django.core.management.base import BaseCommand
import pandas as pd
from security_app.models import Threat, Incident

class Command(BaseCommand):
    help = 'Загрузка данных из Excel-файлов ФСТЭК и инцидентов'
    
    def add_arguments(self, parser):
        parser.add_argument('--threats', type=str, required=True, help='Путь к thrlist.xlsx')
        parser.add_argument('--incidents', type=str, required=True, help='Путь к incidents_2000.xlsx')
    
    def handle(self, *args, **options):
        # Загрузка угроз
        self.stdout.write('Загрузка угроз ФСТЭК...')
        threats_df = pd.read_excel(options['threats'], header=1)
        
        for _, row in threats_df.iterrows():
            Threat.objects.update_or_create(
                threat_id=row['Идентификатор УБИ'],
                defaults={
                    'name': row['Наименование УБИ'],
                    'description': row['Описание'],
                    'threat_source': row['Источник угрозы (характеристика и потенциал нарушителя)'],
                    'target_object': row['Объект воздействия'],
                    'confidentiality_breach': bool(row['Нарушение конфиденциальности']),
                    'integrity_breach': bool(row['Нарушение целостности']),
                    'availability_breach': bool(row['Нарушение доступности']),
                    'date_added': pd.to_datetime(row['Дата включения угрозы в БнД УБИ']).date(),
                    'last_modified': pd.to_datetime(row['Дата последнего изменения данных']).date(),
                    'status': row['Статус угрозы'],
                    'notes': row['Замечания'] if pd.notna(row.get('Замечания')) else None
                }
            )
        self.stdout.write(self.style.SUCCESS(f'✓ Загружено {Threat.objects.count()} угроз'))
        
        self.stdout.write('Загрузка исторических инцидентов...')
        incidents_df = pd.read_excel(options['incidents'])
        
        for _, row in incidents_df.iterrows():
            incident_date = pd.to_datetime(row['Дата инцидента'], dayfirst=True).date()
            
            incident_time = pd.to_datetime(row['Региональное время'], dayfirst=True)
            
            success_value = int(row['Успех']) if pd.notna(row['Успех']) else 0
            success = bool(success_value)
            
            host_count = int(row['Количество хостов']) if pd.notna(row['Количество хостов']) else 0
            
            Incident.objects.update_or_create(
                enterprise_code=str(row['Код предприятия']),
                incident_time=incident_time,
                defaults={
                    'enterprise_type': row['Тип предприятия'],
                    'host_count': host_count,
                    'threat_code': int(row['Код реализованной угрозы']),
                    'success': success,
                    'region': row['Регион размещения предприятия'],
                    'incident_date': incident_date,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'✓ Загружено {Incident.objects.count()} инцидентов'))