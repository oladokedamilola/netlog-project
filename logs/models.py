from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

LOG_TYPES = [
    ("apache", "Apache"),
    ("nginx", "Nginx"),
    ("iis", "IIS"),
]

class LogUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uploads")
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    file = models.FileField(upload_to="logs/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.log_type} - {self.uploaded_at}"


class ParsedEntry(models.Model):
    upload = models.ForeignKey(LogUpload, on_delete=models.CASCADE, related_name="entries")

    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField()
    method = models.CharField(max_length=10, blank=True, null=True)
    status_code = models.IntegerField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["status_code"]),
        ]

    def __str__(self):
        return f"{self.ip_address} - {self.status_code}"
