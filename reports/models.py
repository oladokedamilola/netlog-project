# report/models.py
from django.db import models
from django.contrib.auth import get_user_model
from logs.models import LogUpload
import json

User = get_user_model()

class GeneratedReport(models.Model):
    REPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('html', 'HTML'),
        ('json', 'JSON'),
    ]
    
    REPORT_TYPES = [
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Analysis'),
        ('security', 'Security Report'),
        ('traffic', 'Traffic Analysis'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    upload = models.ForeignKey(LogUpload, on_delete=models.CASCADE, related_name='reports')
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default='summary')
    format = models.CharField(max_length=10, choices=REPORT_FORMATS, default='pdf')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File storage
    file = models.FileField(upload_to='reports/%Y/%m/%d/', blank=True, null=True)
    file_size = models.IntegerField(default=0)
    
    # Report data (stored as JSON for quick access)
    report_data = models.JSONField(default=dict)
    
    # Generation info
    generated_at = models.DateTimeField(auto_now_add=True)
    generation_time = models.FloatField(default=0, help_text='Generation time in seconds')
    
    # Metadata
    is_downloaded = models.BooleanField(default=False)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    download_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['user', 'generated_at']),
            models.Index(fields=['upload', 'report_type']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_format_display()})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('reports:download_report', kwargs={'report_id': self.id})
    
    def mark_downloaded(self):
        """Mark report as downloaded and increment counter"""
        from django.utils import timezone
        self.is_downloaded = True
        self.downloaded_at = timezone.now()
        self.download_count += 1
        self.save()
    
    def get_file_extension(self):
        """Get file extension based on format"""
        extensions = {
            'pdf': '.pdf',
            'csv': '.csv',
            'html': '.html',
            'json': '.json',
        }
        return extensions.get(self.format, '.txt')
    
    def get_content_type(self):
        """Get HTTP content type for download"""
        content_types = {
            'pdf': 'application/pdf',
            'csv': 'text/csv',
            'html': 'text/html',
            'json': 'application/json',
        }
        return content_types.get(self.format, 'text/plain')

class ReportTemplate(models.Model):
    """Template for custom report generation"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Template configuration
    template_type = models.CharField(max_length=20, choices=[
        ('company', 'Company Report'),
        ('security', 'Security Audit'),
        ('developer', 'Developer Report'),
        ('custom', 'Custom'),
    ])
    
    # Template content (HTML template with placeholders)
    html_template = models.TextField(help_text='HTML template with {{ variables }}')
    css_styles = models.TextField(blank=True, help_text='Custom CSS styles')
    
    # Fields to include
    include_summary = models.BooleanField(default=True)
    include_charts = models.BooleanField(default=False)
    include_raw_data = models.BooleanField(default=False)
    include_recommendations = models.BooleanField(default=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates')
    created_at = models.DateTimeField(auto_now_add=True)
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name