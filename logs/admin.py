# logs/admin.py
"""
Logs App Admin Configuration
============================
This module configures the Django admin interface for the logs app models.

It provides customized admin views for managing log uploads and parsed entries,
with enhanced list displays, filters, search capabilities, and inline editing.
"""

from django.contrib import admin
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q
from django.contrib.admin.views.decorators import staff_member_required
import os
import logging

from .models import LogUpload, ParsedEntry, LOG_TYPES

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# PARSED ENTRY ADMIN (INLINE AND MAIN)
# ============================================================================

class ParsedEntryInline(admin.TabularInline):
    """
    Inline admin for ParsedEntry to display within LogUpload admin.
    
    Shows a preview of parsed log entries directly on the upload page.
    """
    model = ParsedEntry
    fk_name = 'upload'
    fields = ('ip_address', 'timestamp', 'method', 'status_code', 
              'url_preview', 'user_agent_preview')
    readonly_fields = ('ip_address', 'timestamp', 'method', 'status_code', 
                      'url_preview', 'user_agent_preview', 'created_at')
    can_delete = False
    extra = 0
    max_num = 20
    ordering = ('-timestamp',)
    
    def url_preview(self, obj):
        """Display truncated URL preview"""
        if obj.url and len(obj.url) > 50:
            return f"{obj.url[:50]}..."
        return obj.url or '-'
    url_preview.short_description = 'URL'
    
    def user_agent_preview(self, obj):
        """Display truncated user agent preview"""
        if obj.user_agent and len(obj.user_agent) > 50:
            return f"{obj.user_agent[:50]}..."
        return obj.user_agent or '-'
    user_agent_preview.short_description = 'User Agent'
    
    def has_add_permission(self, request, obj=None):
        """Prevent adding entries directly in admin"""
        return False


@admin.register(ParsedEntry)
class ParsedEntryAdmin(admin.ModelAdmin):
    """
    Admin configuration for ParsedEntry model.
    
    Provides comprehensive management of parsed log entries with
    advanced filtering, searching, and bulk operations.
    """
    
    list_display = ('id', 'upload_info', 'ip_address', 'timestamp', 
                   'method', 'status_code_display', 'url_preview', 'created_at')
    
    list_filter = ('method', 'status_code', 'timestamp', 'created_at',
                  'upload__log_type', 'upload__user__username')
    
    search_fields = ('ip_address', 'url', 'user_agent', 
                    'upload__filename', 'upload__user__email')
    
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Upload Information', {
            'fields': ('upload',),
            'classes': ('wide',),
        }),
        ('Request Details', {
            'fields': ('ip_address', 'timestamp', 'method', 'status_code', 'url'),
            'classes': ('wide',),
        }),
        ('Client Information', {
            'fields': ('user_agent',),
            'classes': ('wide',),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    actions = ['export_selected_csv', 'delete_selected_entries', 
               'mark_as_404', 'mark_as_error']
    
    def upload_info(self, obj):
        """Display upload information with link"""
        url = reverse('admin:logs_logupload_change', args=[obj.upload.id])
        return format_html(
            '<a href="{}">{}</a><br><small>{}</small>',
            url,
            obj.upload.filename_display(),
            obj.upload.get_log_type_display()
        )
    upload_info.short_description = 'Log Upload'
    upload_info.admin_order_field = 'upload__filename'
    
    def status_code_display(self, obj):
        """Display status code with color coding"""
        if obj.status_code:
            if 200 <= obj.status_code < 300:
                color = 'green'
                icon = '✓'
            elif 300 <= obj.status_code < 400:
                color = 'blue'
                icon = '↪'
            elif 400 <= obj.status_code < 500:
                color = 'orange'
                icon = '⚠'
            elif 500 <= obj.status_code < 600:
                color = 'red'
                icon = '✗'
            else:
                color = 'gray'
                icon = '?'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {}</span>',
                color,
                icon,
                obj.status_code
            )
        return '-'
    status_code_display.short_description = 'Status'
    status_code_display.admin_order_field = 'status_code'
    
    def url_preview(self, obj):
        """Display truncated URL with full URL in tooltip"""
        if obj.url:
            if len(obj.url) > 60:
                return format_html(
                    '<span title="{}">{}</span>',
                    obj.url,
                    f"{obj.url[:60]}..."
                )
            return obj.url
        return '-'
    url_preview.short_description = 'URL'
    
    def export_selected_csv(self, request, queryset):
        """Export selected entries as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="parsed_entries.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Upload ID', 'Upload File', 'IP Address', 'Timestamp', 
            'Method', 'Status Code', 'URL', 'User Agent', 'Created At'
        ])
        
        for entry in queryset.select_related('upload'):
            writer.writerow([
                entry.upload.id,
                entry.upload.filename_display(),
                entry.ip_address,
                entry.timestamp,
                entry.method,
                entry.status_code,
                entry.url,
                entry.user_agent,
                entry.created_at
            ])
        
        logger.info(f"Admin {request.user.username} exported {queryset.count()} parsed entries to CSV")
        return response
    export_selected_csv.short_description = "Export selected as CSV"
    
    def mark_as_404(self, request, queryset):
        """Mark selected entries as 404 errors"""
        updated = queryset.update(status_code=404)
        self.message_user(request, f"Updated {updated} entries to status code 404")
        logger.info(f"Admin {request.user.username} marked {updated} entries as 404")
    mark_as_404.short_description = "Mark as 404 Not Found"
    
    def mark_as_error(self, request, queryset):
        """Mark selected entries as 500 errors"""
        updated = queryset.update(status_code=500)
        self.message_user(request, f"Updated {updated} entries to status code 500")
        logger.info(f"Admin {request.user.username} marked {updated} entries as 500")
    mark_as_error.short_description = "Mark as 500 Server Error"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('upload', 'upload__user')


# ============================================================================
# LOG UPLOAD ADMIN
# ============================================================================

@admin.register(LogUpload)
class LogUploadAdmin(admin.ModelAdmin):
    """
    Admin configuration for LogUpload model.
    
    Provides comprehensive management of log uploads including
    file handling, processing status, and entry previews.
    """
    
    list_display = ('id', 'filename_display', 'user_info', 'log_type_display',
                   'uploaded_at', 'status_display', 'entries_count', 
                   'processing_time', 'file_size_display')
    
    list_filter = ('log_type', 'status', 'uploaded_at', 'processed_at',
                  'user__username', 'user__is_staff')
    
    search_fields = ('user__username', 'user__email', 'file', 'error_message')
    
    readonly_fields = ('uploaded_at', 'processed_at', 'status', 
                      'error_message', 'file_preview')
    
    inlines = [ParsedEntryInline]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',),
            'classes': ('wide',),
        }),
        ('File Information', {
            'fields': ('log_type', 'file', 'file_preview', 'uploaded_at'),
            'classes': ('wide',),
        }),
        ('Processing Status', {
            'fields': ('status', 'processed_at', 'error_message'),
            'classes': ('wide',),
        }),
        ('Statistics', {
            'fields': (),
            'classes': ('wide',),
            'description': 'Statistics will be displayed in the list view'
        }),
    )
    
    actions = ['reprocess_selected', 'mark_as_completed', 
              'mark_as_failed', 'clear_error_messages']
    
    def filename_display(self, obj):
        """Extract filename from file field"""
        if obj.file:
            return os.path.basename(obj.file.name)
        return "No file"
    filename_display.short_description = 'Filename'
    filename_display.admin_order_field = 'file'
    
    def user_info(self, obj):
        """Display user information with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a><br><small>{}</small>',
            url,
            obj.user.username,
            obj.user.email
        )
    user_info.short_description = 'User'
    user_info.admin_order_field = 'user__username'
    
    def log_type_display(self, obj):
        """Display log type with icon"""
        icons = {
            'apache': '🐘',
            'nginx': '🚀',
            'iis': '🪟',
        }
        icon = icons.get(obj.log_type, '📄')
        return f"{icon} {obj.get_log_type_display()}"
    log_type_display.short_description = 'Type'
    log_type_display.admin_order_field = 'log_type'
    
    def status_display(self, obj):
        """Display status with color coding and icon"""
        status_config = {
            'pending': {'color': 'gray', 'icon': '⏳', 'text': 'Pending'},
            'processing': {'color': 'blue', 'icon': '⚙️', 'text': 'Processing'},
            'completed': {'color': 'green', 'icon': '✅', 'text': 'Completed'},
            'failed': {'color': 'red', 'icon': '❌', 'text': 'Failed'},
        }
        
        config = status_config.get(obj.status, {'color': 'gray', 'icon': '❓', 'text': obj.status})
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            config['color'],
            config['icon'],
            config['text']
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def entries_count(self, obj):
        """Display count of parsed entries with link to filter"""
        count = obj.entries.count()
        if count > 0:
            url = reverse('admin:logs_parsedentry_changelist')
            url += f'?upload__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    entries_count.short_description = 'Entries'
    
    def processing_time(self, obj):
        """Calculate and display processing time"""
        if obj.processed_at and obj.uploaded_at:
            delta = obj.processed_at - obj.uploaded_at
            seconds = delta.total_seconds()
            if seconds < 60:
                return f"{seconds:.1f}s"
            else:
                minutes = seconds / 60
                return f"{minutes:.1f}m"
        return '-'
    processing_time.short_description = 'Processing Time'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        if obj.file and obj.file.size:
            size = obj.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return '-'
    file_size_display.short_description = 'File Size'
    
    def file_preview(self, obj):
        """Show file preview information"""
        if obj.file and obj.file.size:
            size = self.file_size_display(obj)
            lines = obj.entries.count()
            
            html = f"""
            <div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
                <p><strong>File:</strong> {os.path.basename(obj.file.name)}</p>
                <p><strong>Size:</strong> {size}</p>
                <p><strong>Parsed Entries:</strong> {lines}</p>
            """
            
            if obj.error_message:
                html += f'<p><strong style="color: red;">Error:</strong> {obj.error_message}</p>'
            
            html += '</div>'
            
            return format_html(html)
        return "No file uploaded"
    file_preview.short_description = 'File Preview'
    
    def reprocess_selected(self, request, queryset):
        """Admin action to reprocess selected uploads"""
        from .utils.parser_selector import get_parser
        from analytics.utils.analyzer import LogAnalyzer
        from analytics.models import Analysis
        
        success_count = 0
        error_count = 0
        
        for upload in queryset:
            try:
                logger.info(f"Reprocessing upload {upload.id}")
                
                # Clear existing entries
                upload.entries.all().delete()
                
                # Parse file again
                file_path = upload.file.path
                parser = get_parser(upload.log_type, file_path)
                
                entries_created = 0
                for row in parser.parse_file():
                    ParsedEntry.objects.create(
                        upload=upload,
                        ip_address=row["ip"],
                        timestamp=row["timestamp"],
                        method=row.get("method", ""),
                        status_code=row.get("status"),
                        url=row.get("url", ""),
                        user_agent=row.get("user_agent", ""),
                    )
                    entries_created += 1
                
                # Update analysis
                analyzer = LogAnalyzer(upload)
                analysis_data = analyzer.analyze()
                
                Analysis.objects.update_or_create(
                    upload=upload,
                    defaults={
                        'user': upload.user,
                        'total_requests': analysis_data['total_requests'],
                        'unique_ips': analysis_data['unique_ips'],
                        'time_period_days': analysis_data['time_period_days'],
                        'avg_requests_per_day': analysis_data['avg_requests_per_day'],
                        'top_ips': analysis_data['top_ips'],
                        'status_codes': analysis_data['status_codes'],
                        'top_endpoints': analysis_data['top_endpoints'],
                        'top_user_agents': analysis_data['top_user_agents'],
                        'hourly_distribution': analysis_data['hourly_distribution'],
                        'daily_distribution': analysis_data['daily_distribution'],
                        'suspicious_ips': analysis_data['suspicious_ips'],
                        'error_rate': analysis_data['error_rate'],
                    }
                )
                
                upload.status = 'completed'
                upload.processed_at = timezone.now()
                upload.error_message = None
                upload.save()
                
                success_count += 1
                logger.info(f"Successfully reprocessed upload {upload.id} with {entries_created} entries")
                
            except Exception as e:
                error_count += 1
                upload.status = 'failed'
                upload.error_message = str(e)[:200]
                upload.save()
                logger.error(f"Failed to reprocess upload {upload.id}: {str(e)}")
        
        self.message_user(
            request,
            f"Reprocessed {success_count} upload(s). Failed: {error_count}"
        )
    reprocess_selected.short_description = "Reprocess selected uploads"
    
    def mark_as_completed(self, request, queryset):
        """Manually mark selected uploads as completed"""
        updated = queryset.update(
            status='completed',
            processed_at=timezone.now()
        )
        self.message_user(request, f"Marked {updated} upload(s) as completed")
        logger.info(f"Admin {request.user.username} marked {updated} uploads as completed")
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_failed(self, request, queryset):
        """Manually mark selected uploads as failed"""
        updated = queryset.update(
            status='failed',
            error_message="Manually marked as failed by admin"
        )
        self.message_user(request, f"Marked {updated} upload(s) as failed")
        logger.info(f"Admin {request.user.username} marked {updated} uploads as failed")
    mark_as_failed.short_description = "Mark as failed"
    
    def clear_error_messages(self, request, queryset):
        """Clear error messages from selected uploads"""
        updated = queryset.update(error_message=None)
        self.message_user(request, f"Cleared error messages for {updated} upload(s)")
        logger.info(f"Admin {request.user.username} cleared errors for {updated} uploads")
    clear_error_messages.short_description = "Clear error messages"
    
    def get_queryset(self, request):
        """Optimize queryset with annotations for performance"""
        return super().get_queryset(request).select_related('user').annotate(
            entry_count=Count('entries')
        )
    
    class Media:
        """Add custom CSS for admin styling"""
        css = {
            'all': ('admin/css/logs_admin.css',)
        }


# ============================================================================
# CUSTOM ADMIN VIEWS AND DASHBOARD
# ============================================================================

class LogsDashboard:
    """
    Helper class for logs dashboard statistics.
    Can be used in custom admin templates.
    """
    
    @staticmethod
    def get_stats():
        """Get summary statistics for logs dashboard"""
        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)
        last_7d = now - timezone.timedelta(days=7)
        last_30d = now - timezone.timedelta(days=30)
        
        stats = {
            'total_uploads': LogUpload.objects.count(),
            'total_entries': ParsedEntry.objects.count(),
            'uploads_today': LogUpload.objects.filter(uploaded_at__gte=last_24h).count(),
            'uploads_week': LogUpload.objects.filter(uploaded_at__gte=last_7d).count(),
            'uploads_month': LogUpload.objects.filter(uploaded_at__gte=last_30d).count(),
            'pending_uploads': LogUpload.objects.filter(status='pending').count(),
            'processing_uploads': LogUpload.objects.filter(status='processing').count(),
            'completed_uploads': LogUpload.objects.filter(status='completed').count(),
            'failed_uploads': LogUpload.objects.filter(status='failed').count(),
        }
        
        # Status code distribution
        stats['success_entries'] = ParsedEntry.objects.filter(
            status_code__gte=200, status_code__lt=300
        ).count()
        stats['redirect_entries'] = ParsedEntry.objects.filter(
            status_code__gte=300, status_code__lt=400
        ).count()
        stats['client_error_entries'] = ParsedEntry.objects.filter(
            status_code__gte=400, status_code__lt=500
        ).count()
        stats['server_error_entries'] = ParsedEntry.objects.filter(
            status_code__gte=500, status_code__lt=600
        ).count()
        
        # Log type distribution
        stats['log_type_counts'] = {}
        for log_type, display in LOG_TYPES:
            stats['log_type_counts'][display] = LogUpload.objects.filter(log_type=log_type).count()
        
        return stats


@staff_member_required
def logs_admin_dashboard(request):
    """
    Custom admin dashboard view for logs statistics.
    """
    stats = LogsDashboard.get_stats()
    
    # Get recent uploads
    recent_uploads = LogUpload.objects.select_related('user').order_by('-uploaded_at')[:10]
    
    # Get failed uploads
    failed_uploads = LogUpload.objects.filter(
        status='failed'
    ).select_related('user').order_by('-uploaded_at')[:10]
    
    # Get top IPs
    top_ips = ParsedEntry.objects.values('ip_address').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    context = {
        'stats': stats,
        'recent_uploads': recent_uploads,
        'failed_uploads': failed_uploads,
        'top_ips': top_ips,
        'title': 'Logs Dashboard',
    }
    
    return render(request, 'admin/logs/dashboard.html', context)


# ============================================================================
# URL CONFIGURATION FOR CUSTOM ADMIN VIEWS
# ============================================================================

from django.urls import path
from django.shortcuts import render

def get_admin_urls():
    """Add custom admin URLs for logs"""
    urls = [
        path('logs-dashboard/', logs_admin_dashboard, name='logs_dashboard'),
    ]
    return urls

# Uncomment to add custom URLs to admin
# admin.site.get_urls = get_admin_urls