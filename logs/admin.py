# logs/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import LogUpload, ParsedEntry

class ParsedEntryInline(admin.TabularInline):
    model = ParsedEntry
    extra = 0
    readonly_fields = ('ip_address', 'timestamp', 'method', 'status_code', 'url', 'user_agent', 'created_at')
    can_delete = False
    fields = ('ip_address', 'timestamp', 'method', 'status_code', 'url_preview', 'user_agent_preview', 'created_at')
    
    def url_preview(self, obj):
        if obj.url and len(obj.url) > 50:
            return f"{obj.url[:50]}..."
        return obj.url or "-"
    url_preview.short_description = 'URL'
    
    def user_agent_preview(self, obj):
        if obj.user_agent and len(obj.user_agent) > 40:
            return f"{obj.user_agent[:40]}..."
        return obj.user_agent or "-"
    user_agent_preview.short_description = 'User Agent'

@admin.register(LogUpload)
class LogUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'log_type', 'file_link', 'uploaded_at', 'entry_count')
    list_filter = ('log_type', 'uploaded_at', 'user')
    search_fields = ('user__email', 'user__username', 'file')
    readonly_fields = ('uploaded_at', 'file_link', 'entry_count_display')
    fieldsets = (
        (None, {
            'fields': ('user', 'log_type', 'file')
        }),
        ('Statistics', {
            'fields': ('entry_count_display', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [ParsedEntryInline]
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__email'
    
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">View/Download</a>', obj.file.url)
        return "-"
    file_link.short_description = 'File'
    
    def entry_count(self, obj):
        return obj.entries.count()
    entry_count.short_description = 'Entries'
    
    def entry_count_display(self, obj):
        return obj.entries.count()
    entry_count_display.short_description = 'Number of parsed entries'

@admin.register(ParsedEntry)
class ParsedEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'upload_link', 'ip_address', 'timestamp', 'method', 'status_code', 'url_preview', 'created_at')
    list_filter = ('status_code', 'method', 'timestamp', 'upload__log_type')
    search_fields = ('ip_address', 'url', 'user_agent', 'upload__user__email')
    readonly_fields = ('created_at', 'upload_link')
    fieldsets = (
        ('Upload Information', {
            'fields': ('upload_link',)
        }),
        ('Log Entry Details', {
            'fields': ('ip_address', 'timestamp', 'method', 'status_code', 'url', 'user_agent')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def upload_link(self, obj):
        url = reverse('admin:logs_logupload_change', args=[obj.upload.id])
        return format_html('<a href="{}">{} - {}</a>', url, obj.upload.user.email, obj.upload.log_type)
    upload_link.short_description = 'Upload'
    
    def url_preview(self, obj):
        if obj.url and len(obj.url) > 40:
            return f"{obj.url[:40]}..."
        return obj.url or "-"
    url_preview.short_description = 'URL'
    
    # Optimize database queries
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('upload', 'upload__user')