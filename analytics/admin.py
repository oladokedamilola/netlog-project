from django.contrib import admin
from .models import Analysis, DashboardMetric

@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'upload', 'total_requests', 'unique_ips', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('user__username', 'user__email', 'upload__filename')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'upload', 'created_at', 'updated_at')
        }),
        ('Metrics', {
            'fields': ('total_requests', 'unique_ips', 'time_period_days', 'avg_requests_per_day', 'error_rate')
        }),
        ('Top Data', {
            'fields': ('top_ips', 'status_codes', 'top_endpoints', 'top_user_agents'),
            'classes': ('collapse',)
        }),
        ('Distributions', {
            'fields': ('hourly_distribution', 'daily_distribution'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('suspicious_ips',),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make all fields readonly when viewing (not adding)
        """
        if obj:  # editing an existing object
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields
    
    def has_add_permission(self, request):
        """
        Prevent adding analyses from admin (they should be created automatically)
        """
        return False

@admin.register(DashboardMetric)
class DashboardMetricAdmin(admin.ModelAdmin):
    list_display = ('user', 'metric_date', 'total_uploads', 'total_requests_analyzed', 'avg_requests_per_upload')
    list_filter = ('metric_date', 'user')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('metric_date',)
    date_hierarchy = 'metric_date'
    
    def has_add_permission(self, request):
        """
        Prevent manual addition (should be created automatically)
        """
        return False
    
    def has_change_permission(self, request, obj=None):
        """
        Prevent editing (should be updated automatically)
        """
        return False