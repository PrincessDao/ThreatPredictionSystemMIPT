from django.urls import path
from .views import IncidentListView

urlpatterns = [
    path("incidents/", IncidentListView.as_view(), name="incidents-list"),
]