# analytiics/models.py

from django.db import models
from django.contrib.auth import get_user_model
from logs.models import LogUpload, ParsedEntry
import json

User = get_user_model()

class Analysis(models.Model):
    """
    Stores analysis results for a log upload
    """
    upload = models.OneToOneField(LogUpload, on_delete=models.CASCADE, related_name='analysis')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Summary metrics
    total_requests = models.IntegerField(default=0)
    unique_ips = models.IntegerField(default=0)
    time_period_days = models.FloatField(default=0)
    avg_requests_per_day = models.FloatField(default=0)
    
    # JSON fields for storing aggregated data
    top_ips = models.JSONField(default=dict, help_text="Top IP addresses with request counts")
    status_codes = models.JSONField(default=dict, help_text="Status code distribution")
    top_endpoints = models.JSONField(default=dict, help_text="Most accessed URLs")
    top_user_agents = models.JSONField(default=dict, help_text="Most common user agents")
    hourly_distribution = models.JSONField(default=dict, help_text="Requests per hour of day")
    daily_distribution = models.JSONField(default=dict, help_text="Requests per day")
    
    # Security metrics
    suspicious_ips = models.JSONField(default=list, help_text="List of potentially suspicious IPs")
    error_rate = models.FloatField(default=0, help_text="Percentage of error responses")
    
    class Meta:
        verbose_name_plural = "Analyses"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Analysis for {self.upload.filename}"

class DashboardMetric(models.Model):
    """
    Stores dashboard metrics for quick access
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_metrics')
    metric_date = models.DateField(auto_now_add=True)
    
    total_uploads = models.IntegerField(default=0)
    total_requests_analyzed = models.IntegerField(default=0)
    avg_requests_per_upload = models.FloatField(default=0)
    last_upload_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'metric_date']
    
    def __str__(self):
        return f"Metrics for {self.user.email} on {self.metric_date}"