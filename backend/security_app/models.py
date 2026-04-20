from django.db import models

class Threat(models.Model):
    """Угрозы из базы ФСТЭК"""
    threat_id = models.IntegerField(primary_key=True, db_column='Идентификатор УБИ')
    name = models.CharField(max_length=500, db_column='Наименование УБИ')
    description = models.TextField(db_column='Описание')
    threat_source = models.TextField(db_column='Источник угрозы')
    target_object = models.CharField(db_column='Объект воздействия')
    
    confidentiality_breach = models.BooleanField(db_column='Нарушение конфиденциальности')
    integrity_breach = models.BooleanField(db_column='Нарушение целостности')
    availability_breach = models.BooleanField(db_column='Нарушение доступности')
    
    date_added = models.DateField(db_column='Дата включения угрозы в БнД УБИ')
    last_modified = models.DateField(db_column='Дата последнего изменения данных')
    status = models.CharField(max_length=50, db_column='Статус угрозы')
    notes = models.TextField(db_column='Замечания', blank=True, null=True)
    
    class Meta:
        db_table = 'fstec_threats'
        verbose_name = 'Угроза ФСТЭК'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['target_object']),
        ]

    def __str__(self):
        return f"Угроза {self.threat_id}: {self.name}"


class Incident(models.Model):
    """Исторические инциденты из incidents_2000.xlsx"""
    enterprise_type = models.CharField(max_length=255, db_column='Тип предприятия')
    enterprise_code = models.CharField(max_length=10, db_column='Код предприятия', db_index=True)
    host_count = models.IntegerField(db_column='Количество хостов', default=0)
    threat_code = models.IntegerField(db_column='Код реализованной угрозы', db_index=True)
    success = models.BooleanField(db_column='Успех', default=False)
    region = models.CharField(max_length=255, db_column='Регион размещения предприятия')
    incident_date = models.DateField(db_column='Дата инцидента')
    incident_time = models.DateTimeField(db_column='Региональное время')

    class Meta:
        db_table = 'security_incidents'
        verbose_name = 'Инцидент безопасности'
        indexes = [
            models.Index(fields=['incident_date', 'threat_code']),
            models.Index(fields=['region', 'enterprise_type']),
            models.Index(fields=['-incident_time']),
        ]

    def __str__(self):
        return f"Инцидент {self.enterprise_code} | Угроза {self.threat_code} | {self.region}"