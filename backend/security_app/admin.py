from django.contrib import admin
from .models import Threat, Incident


# ----------------------------
# УГРОЗЫ ФСТЭК
# ----------------------------
@admin.register(Threat)
class ThreatAdmin(admin.ModelAdmin):
    # Перечисляем методы, чтобы контролировать заголовки и формат
    list_display = (
        'threat_id_display',
        'name_display',
        'description_display',
        'source_display',
        'target_display',
        'confidentiality_display',
        'integrity_display',
        'availability_display',
        'date_added_display',
        'last_modified_display',
        'status_display',
        'notes_display',
    )

    list_filter = ('status', 'target_object')
    search_fields = ('name', 'threat_id', 'description')

    # --- Методы отображения (Заголовки как в Excel) ---

    @admin.display(description="Идентификатор УБИ", ordering='threat_id')
    def threat_id_display(self, obj):
        return obj.threat_id

    @admin.display(description="Наименование УБИ", ordering='name')
    def name_display(self, obj):
        return obj.name

    @admin.display(description="Описание", ordering='description')
    def description_display(self, obj):
        # Обрезаем длинное описание, чтобы таблица не разъезжалась
        if obj.description:
            return str(obj.description)[:50] + "..." if len(obj.description) > 50 else obj.description
        return ""

    @admin.display(description="Источник угрозы (характеристика и потенциал нарушителя)", ordering='threat_source')
    def source_display(self, obj):
        if obj.threat_source:
            return str(obj.threat_source)[:40] + "..." if len(obj.threat_source) > 40 else obj.threat_source
        return ""

    @admin.display(description="Объект воздействия", ordering='target_object')
    def target_display(self, obj):
        return obj.target_object

    @admin.display(description="Нарушение конфиденциальности", ordering='confidentiality_breach')
    def confidentiality_display(self, obj):
        # Возвращаем 1 или 0 вместо галочек
        return 1 if obj.confidentiality_breach else 0

    @admin.display(description="Нарушение целостности", ordering='integrity_breach')
    def integrity_display(self, obj):
        return 1 if obj.integrity_breach else 0

    @admin.display(description="Нарушение доступности", ordering='availability_breach')
    def availability_display(self, obj):
        return 1 if obj.availability_breach else 0

    @admin.display(description="Дата включения угрозы в БнД УБИ", ordering='date_added')
    def date_added_display(self, obj):
        if obj.date_added:
            return obj.date_added.strftime('%d.%m.%Y')
        return ""

    @admin.display(description="Дата последнего изменения данных", ordering='last_modified')
    def last_modified_display(self, obj):
        if obj.last_modified:
            return obj.last_modified.strftime('%d.%m.%Y')
        return ""

    @admin.display(description="Статус угрозы", ordering='status')
    def status_display(self, obj):
        return obj.status

    @admin.display(description="Замечания", ordering='notes')
    def notes_display(self, obj):
        return obj.notes if obj.notes else ""


# ----------------------------
# ИНЦИДЕНТЫ
# ----------------------------
@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        'enterprise_type_display',
        'enterprise_code_display',
        'host_count_display',
        'threat_code_display',
        'success_display',
        'region_display',
        'incident_date_display',
        'incident_time_display',
    )

    list_filter = ('success', 'region', 'enterprise_type', 'threat_code')
    search_fields = ('enterprise_code', 'region', 'enterprise_type')
    date_hierarchy = 'incident_date'
    ordering = ('-incident_date', '-incident_time')

    @admin.display(description="Тип предприятия", ordering='enterprise_type')
    def enterprise_type_display(self, obj):
        return obj.enterprise_type

    @admin.display(description="Код предприятия", ordering='enterprise_code')
    def enterprise_code_display(self, obj):
        return obj.enterprise_code

    @admin.display(description="Количество хостов", ordering='host_count')
    def host_count_display(self, obj):
        return obj.host_count

    @admin.display(description="Код реализованной угрозы", ordering='threat_code')
    def threat_code_display(self, obj):
        return obj.threat_code

    @admin.display(description="Успех", ordering='success')
    def success_display(self, obj):
        return "1" if obj.success else "0"

    @admin.display(description="Регион размещения предприятия", ordering='region')
    def region_display(self, obj):
        return obj.region

    @admin.display(description="Дата инцидента", ordering='incident_date')
    def incident_date_display(self, obj):
        if obj.incident_date:
            return obj.incident_date.strftime('%d.%m.%Y')
        return ""

    @admin.display(description="Региональное время", ordering='incident_time')
    def incident_time_display(self, obj):
        if obj.incident_time:
            return obj.incident_time.strftime('%d.%m.%Y %H:%M')
        return ""