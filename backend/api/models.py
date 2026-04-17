from django.db import models


class Incident(models.Model):
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Incident {self.id} at {self.created_at}"