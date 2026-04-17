from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Incident
from .serializers import IncidentSerializer


class IncidentListView(APIView):
    def get(self, request):
        qs = Incident.objects.all().order_by("-created_at")[:200]
        serializer = IncidentSerializer(qs, many=True)
        return Response(serializer.data)