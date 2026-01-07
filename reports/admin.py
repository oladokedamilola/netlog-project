# reports/admin.py

from django.contrib import admin
from .models import GeneratedReport, ReportTemplate

@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'report_type', 'format', 'generated_at', 'file_size', 'download_count')
    list_filter = ('report_type', 'format', 'generated_at', 'user')
    search_fields = ('title', 'description', 'user__username', 'user__email', 'upload__filename')
    readonly_fields = ('generated_at', 'generation_time', 'file_size', 'download_count', 'downloaded_at')
    date_hierarchy = 'generated_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'upload', 'title', 'description')
        }),
        ('Report Configuration', {
            'fields': ('report_type', 'format', 'report_data')
        }),
        ('File Information', {
            'fields': ('file', 'file_size', 'generation_time')
        }),
        ('Download Statistics', {
            'fields': ('download_count', 'is_downloaded', 'downloaded_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('generated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('user', 'upload', 'report_type', 'format')
        return self.readonly_fields
    
    def has_add_permission(self, request):
        """
        Prevent manual addition - reports should be generated through the app
        """
        return False

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'created_by', 'created_at', 'is_default', 'is_public')
    list_filter = ('template_type', 'is_default', 'is_public', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'template_type', 'created_by')
        }),
        ('Template Content', {
            'fields': ('html_template', 'css_styles')
        }),
        ('Content Options', {
            'fields': ('include_summary', 'include_charts', 'include_raw_data', 'include_recommendations'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_default', 'is_public')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)