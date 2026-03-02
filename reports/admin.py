# reports/admin.py
"""
Reports App Admin Configuration
===============================
This module configures the Django admin interface for the reports app models.

It provides customized admin views for managing generated reports and report templates,
with enhanced list displays, filters, search capabilities, and inline editing.
"""

from django.contrib import admin
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q
from django.contrib.admin.views.decorators import staff_member_required
import os
import json
import logging
from django.db import models
from .models import GeneratedReport, ReportTemplate

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# GENERATED REPORT ADMIN
# ============================================================================

@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    """
    Admin configuration for GeneratedReport model.
    
    Provides comprehensive management of generated reports including
    file handling, download tracking, and report preview capabilities.
    """
    
    list_display = ('id', 'title_display', 'user_info', 'upload_info', 
                   'report_type_display', 'format_display', 'generated_at', 
                   'file_size_display', 'download_stats', 'actions_buttons')
    
    list_filter = ('report_type', 'format', 'generated_at', 'is_downloaded',
                  'user__username', 'upload__log_type')
    
    search_fields = ('title', 'description', 'user__username', 'user__email',
                    'upload__filename')
    
    readonly_fields = ('generated_at', 'file_size', 'download_count', 
                      'downloaded_at', 'file_preview', 'report_data_preview')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'upload', 'title', 'description'),
            'classes': ('wide',),
        }),
        ('Report Configuration', {
            'fields': ('report_type', 'format'),
            'classes': ('wide',),
        }),
        ('File Information', {
            'fields': ('file', 'file_preview', 'file_size', 'generated_at'),
            'classes': ('wide',),
        }),
        ('Download Statistics', {
            'fields': ('download_count', 'is_downloaded', 'downloaded_at'),
            'classes': ('wide',),
        }),
        ('Report Data', {
            'fields': ('report_data_preview',),
            'classes': ('wide', 'collapse'),
            'description': 'Raw report data stored as JSON'
        }),
        ('Generation Info', {
            'fields': ('generation_time',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    actions = ['mark_as_downloaded', 'reset_download_stats', 
               'regenerate_report', 'export_report_metadata']
    
    def title_display(self, obj):
        """Display title with truncation"""
        if len(obj.title) > 50:
            return format_html(
                '<span title="{}">{}</span>',
                obj.title,
                f"{obj.title[:50]}..."
            )
        return obj.title
    title_display.short_description = 'Title'
    title_display.admin_order_field = 'title'
    
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
    
    def upload_info(self, obj):
        """Display upload information with link"""
        url = reverse('admin:logs_logupload_change', args=[obj.upload.id])
        return format_html(
            '<a href="{}">{}</a><br><small>{}</small>',
            url,
            obj.upload.filename_display() if hasattr(obj.upload, 'filename_display') else f"Upload #{obj.upload.id}",
            obj.upload.get_log_type_display() if hasattr(obj.upload, 'get_log_type_display') else ''
        )
    upload_info.short_description = 'Log Upload'
    upload_info.admin_order_field = 'upload__filename'
    
    def report_type_display(self, obj):
        """Display report type with icon"""
        icons = {
            'summary': '📊',
            'detailed': '📈',
            'security': '🔒',
            'traffic': '🚦',
        }
        icon = icons.get(obj.report_type, '📄')
        return f"{icon} {obj.get_report_type_display()}"
    report_type_display.short_description = 'Type'
    report_type_display.admin_order_field = 'report_type'
    
    def format_display(self, obj):
        """Display format with color coding"""
        colors = {
            'pdf': 'red',
            'csv': 'green',
            'html': 'blue',
            'json': 'purple',
        }
        color = colors.get(obj.format, 'gray')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_format_display().upper()
        )
    format_display.short_description = 'Format'
    format_display.admin_order_field = 'format'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} GB"
        return '-'
    file_size_display.short_description = 'Size'
    
    def download_stats(self, obj):
        """Display download statistics"""
        if obj.download_count > 0:
            color = 'green' if obj.download_count > 5 else 'blue'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} downloads</span>',
                color,
                obj.download_count
            )
        return format_html(
            '<span style="color: gray;">Not downloaded</span>'
        )
    download_stats.short_description = 'Downloads'
    
    def actions_buttons(self, obj):
        """Display action buttons for quick access"""
        download_url = reverse('reports:download_report', kwargs={'report_id': obj.id})
        detail_url = reverse('reports:report_detail', kwargs={'report_id': obj.id})
        
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background: #28a745; margin-right: 5px;">⬇️ Download</a>'
            '<a class="button" href="{}" target="_blank" style="background: #17a2b8;">👁️ View</a>',
            download_url,
            detail_url
        )
    actions_buttons.short_description = 'Actions'
    
    def file_preview(self, obj):
        """Show file preview information"""
        if obj.file and obj.file.name:
            html = f"""
            <div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
                <p><strong>Filename:</strong> {os.path.basename(obj.file.name)}</p>
                <p><strong>Size:</strong> {self.file_size_display(obj)}</p>
                <p><strong>Format:</strong> {obj.get_format_display()}</p>
            """
            
            # Add download button for existing file
            if obj.file:
                url = reverse('reports:download_report', kwargs={'report_id': obj.id})
                html += f'<p><a class="button" href="{url}" target="_blank" style="background: #28a745;">⬇️ Download Report</a></p>'
            
            html += '</div>'
            
            return format_html(html)
        return "No file attached"
    file_preview.short_description = 'File Preview'
    
    def report_data_preview(self, obj):
        """Display formatted report data preview"""
        if obj.report_data:
            # Get a preview of the report data
            preview = {}
            
            # Include key fields for preview
            for key in ['title', 'report_type', 'filters', 'options']:
                if key in obj.report_data:
                    preview[key] = obj.report_data[key]
            
            # Format as pretty JSON
            formatted_json = json.dumps(preview, indent=2, default=str)
            
            # Truncate if too long
            if len(formatted_json) > 2000:
                formatted_json = formatted_json[:2000] + "\n... (truncated)"
            
            return format_html(
                '<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow: auto; max-height: 400px;">{}</pre>',
                formatted_json
            )
        return "No report data stored"
    report_data_preview.short_description = 'Report Data Preview'
    
    def mark_as_downloaded(self, request, queryset):
        """Manually mark reports as downloaded"""
        now = timezone.now()
        updated = queryset.update(
            is_downloaded=True,
            downloaded_at=now,
            download_count=models.F('download_count') + 1
        )
        self.message_user(request, f"Marked {updated} report(s) as downloaded")
        logger.info(f"Admin {request.user.username} marked {updated} reports as downloaded")
    mark_as_downloaded.short_description = "Mark as downloaded"
    
    def reset_download_stats(self, request, queryset):
        """Reset download statistics"""
        updated = queryset.update(
            is_downloaded=False,
            downloaded_at=None,
            download_count=0
        )
        self.message_user(request, f"Reset download stats for {updated} report(s)")
        logger.info(f"Admin {request.user.username} reset download stats for {updated} reports")
    reset_download_stats.short_description = "Reset download stats"
    
    def regenerate_report(self, request, queryset):
        """Regenerate selected reports"""
        from .utils.report_generators import (
            generate_pdf_report, generate_csv_report, 
            generate_html_report, generate_json_report
        )
        from django.core.files.base import ContentFile
        
        success_count = 0
        error_count = 0
        
        for report in queryset:
            try:
                logger.info(f"Regenerating report {report.id}")
                
                # Determine generator function based on format
                generators = {
                    'pdf': generate_pdf_report,
                    'csv': generate_csv_report,
                    'html': generate_html_report,
                    'json': generate_json_report,
                }
                
                generator = generators.get(report.format)
                if not generator:
                    raise ValueError(f"Unsupported format: {report.format}")
                
                # Generate new content
                file_content = generator(report.report_data)
                
                # Update file
                if report.file:
                    report.file.delete(save=False)
                
                filename = f"report_{report.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}{report.get_file_extension()}"
                report.file.save(filename, ContentFile(file_content))
                report.file_size = len(file_content)
                report.generated_at = timezone.now()
                report.save()
                
                success_count += 1
                logger.info(f"Successfully regenerated report {report.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to regenerate report {report.id}: {str(e)}")
        
        self.message_user(
            request,
            f"Regenerated {success_count} report(s). Failed: {error_count}"
        )
    regenerate_report.short_description = "Regenerate selected reports"
    
    def export_report_metadata(self, request, queryset):
        """Export report metadata as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="report_metadata.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Report ID', 'Title', 'User', 'Upload ID', 'Report Type', 
            'Format', 'Generated At', 'File Size', 'Download Count'
        ])
        
        for report in queryset.select_related('user', 'upload'):
            writer.writerow([
                report.id,
                report.title,
                report.user.username,
                report.upload.id,
                report.get_report_type_display(),
                report.get_format_display(),
                report.generated_at,
                report.file_size,
                report.download_count
            ])
        
        logger.info(f"Admin {request.user.username} exported metadata for {queryset.count()} reports")
        return response
    export_report_metadata.short_description = "Export metadata as CSV"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user', 'upload')
    
    class Media:
        """Add custom CSS for admin styling"""
        css = {
            'all': ('admin/css/reports_admin.css',)
        }


# ============================================================================
# REPORT TEMPLATE ADMIN
# ============================================================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    """
    Admin configuration for ReportTemplate model.
    
    Provides comprehensive management of report templates including
    template preview and configuration options.
    """
    
    list_display = ('name', 'template_type_display', 'created_by_info', 
                   'created_at', 'status_display', 'includes_display', 
                   'usage_count', 'actions_buttons')
    
    list_filter = ('template_type', 'is_default', 'is_public', 
                  'created_at', 'created_by__username')
    
    search_fields = ('name', 'description', 'created_by__username', 
                    'created_by__email')
    
    readonly_fields = ('created_at', 'template_preview')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'template_type', 'created_by'),
            'classes': ('wide',),
        }),
        ('Template Content', {
            'fields': ('html_template', 'css_styles', 'template_preview'),
            'classes': ('wide',),
        }),
        ('Inclusion Options', {
            'fields': ('include_summary', 'include_charts', 
                      'include_raw_data', 'include_recommendations'),
            'classes': ('wide',),
        }),
        ('Visibility', {
            'fields': ('is_default', 'is_public'),
            'classes': ('wide',),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    actions = ['set_as_default', 'make_public', 'make_private', 'duplicate_template']
    
    def template_type_display(self, obj):
        """Display template type with icon"""
        icons = {
            'company': '🏢',
            'security': '🔒',
            'developer': '👨‍💻',
            'custom': '⚙️',
        }
        icon = icons.get(obj.template_type, '📄')
        return f"{icon} {obj.get_template_type_display()}"
    template_type_display.short_description = 'Type'
    template_type_display.admin_order_field = 'template_type'
    
    def created_by_info(self, obj):
        """Display creator information with link"""
        url = reverse('admin:auth_user_change', args=[obj.created_by.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.created_by.username
        )
    created_by_info.short_description = 'Created By'
    created_by_info.admin_order_field = 'created_by__username'
    
    def status_display(self, obj):
        """Display template status with color coding"""
        status_html = []
        
        if obj.is_default:
            status_html.append(format_html(
                '<span style="color: green; font-weight: bold;">★ Default</span>'
            ))
        
        if obj.is_public:
            status_html.append(format_html(
                '<span style="color: blue;">🌐 Public</span>'
            ))
        else:
            status_html.append(format_html(
                '<span style="color: gray;">🔒 Private</span>'
            ))
        
        return format_html('{}', ' '.join(str(s) for s in status_html))
    status_display.short_description = 'Status'
    
    def includes_display(self, obj):
        """Display included components"""
        includes = []
        
        if obj.include_summary:
            includes.append('📊 Summary')
        if obj.include_charts:
            includes.append('📈 Charts')
        if obj.include_raw_data:
            includes.append('📋 Raw Data')
        if obj.include_recommendations:
            includes.append('💡 Recommendations')
        
        if not includes:
            return format_html('<span style="color: gray;">No components</span>')
        
        return format_html('<br>'.join(includes))
    includes_display.short_description = 'Includes'
    
    def usage_count(self, obj):
        """Count how many reports use this template"""
        # This would require a relation between reports and templates
        # For now, return placeholder
        count = 0  # Replace with actual count when relation exists
        return count
    usage_count.short_description = 'Usage'
    
    def actions_buttons(self, obj):
        """Display action buttons for quick access"""
        preview_url = f"#preview-{obj.id}"  # Add actual preview URL when implemented
        
        buttons = []
        
        if obj.is_default:
            buttons.append('<span style="color: green;">★ Default</span>')
        else:
            buttons.append(format_html(
                '<a class="button" href="#" onclick="return false;" style="background: #ffc107;">★ Set Default</a>'
            ))
        
        return format_html('{}', ' '.join(buttons))
    actions_buttons.short_description = 'Actions'
    
    def template_preview(self, obj):
        """Show template preview"""
        if obj.html_template:
            # Create a simple preview with placeholders highlighted
            preview = obj.html_template[:500] + "..." if len(obj.html_template) > 500 else obj.html_template
            
            # Highlight variables
            import re
            preview = re.sub(r'{{(.*?)}}', r'<span style="background: #fff3cd; padding: 2px 4px; border-radius: 3px;">{{\1}}</span>', preview)
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace; white-space: pre-wrap;">{}</div>',
                preview
            )
        return "No template content"
    template_preview.short_description = 'Template Preview'
    
    def set_as_default(self, request, queryset):
        """Set selected templates as default"""
        # Clear existing defaults
        ReportTemplate.objects.filter(is_default=True).update(is_default=False)
        
        # Set new defaults
        updated = queryset.update(is_default=True)
        self.message_user(request, f"Set {updated} template(s) as default")
        logger.info(f"Admin {request.user.username} set {updated} templates as default")
    set_as_default.short_description = "Set as default template"
    
    def make_public(self, request, queryset):
        """Make selected templates public"""
        updated = queryset.update(is_public=True)
        self.message_user(request, f"Made {updated} template(s) public")
        logger.info(f"Admin {request.user.username} made {updated} templates public")
    make_public.short_description = "Make public"
    
    def make_private(self, request, queryset):
        """Make selected templates private"""
        updated = queryset.update(is_public=False)
        self.message_user(request, f"Made {updated} template(s) private")
        logger.info(f"Admin {request.user.username} made {updated} templates private")
    make_private.short_description = "Make private"
    
    def duplicate_template(self, request, queryset):
        """Duplicate selected templates"""
        for template in queryset:
            template.pk = None
            template.name = f"{template.name} (Copy)"
            template.is_default = False
            template.created_at = timezone.now()
            template.save()
        
        self.message_user(request, f"Duplicated {queryset.count()} template(s)")
        logger.info(f"Admin {request.user.username} duplicated {queryset.count()} templates")
    duplicate_template.short_description = "Duplicate template"
    
    def save_model(self, request, obj, form, change):
        """Override save to set created_by automatically"""
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('created_by')


# ============================================================================
# CUSTOM ADMIN VIEWS AND DASHBOARD
# ============================================================================

class ReportsDashboard:
    """
    Helper class for reports dashboard statistics.
    Can be used in custom admin templates.
    """
    
    @staticmethod
    def get_stats():
        """Get summary statistics for reports dashboard"""
        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)
        last_7d = now - timezone.timedelta(days=7)
        last_30d = now - timezone.timedelta(days=30)
        
        stats = {
            'total_reports': GeneratedReport.objects.count(),
            'reports_today': GeneratedReport.objects.filter(generated_at__gte=last_24h).count(),
            'reports_week': GeneratedReport.objects.filter(generated_at__gte=last_7d).count(),
            'reports_month': GeneratedReport.objects.filter(generated_at__gte=last_30d).count(),
            'total_templates': ReportTemplate.objects.count(),
            'public_templates': ReportTemplate.objects.filter(is_public=True).count(),
            'total_downloads': GeneratedReport.objects.aggregate(
                total=Sum('download_count')
            )['total'] or 0,
            'avg_generation_time': GeneratedReport.objects.aggregate(
                avg=models.Avg('generation_time')
            )['avg'] or 0,
        }
        
        # Format distribution
        stats['format_distribution'] = {}
        for format_code, format_name in GeneratedReport.REPORT_FORMATS:
            stats['format_distribution'][format_name] = GeneratedReport.objects.filter(
                format=format_code
            ).count()
        
        # Type distribution
        stats['type_distribution'] = {}
        for type_code, type_name in GeneratedReport.REPORT_TYPES:
            stats['type_distribution'][type_name] = GeneratedReport.objects.filter(
                report_type=type_code
            ).count()
        
        return stats


@staff_member_required
def reports_admin_dashboard(request):
    """
    Custom admin dashboard view for reports statistics.
    """
    stats = ReportsDashboard.get_stats()
    
    # Get recent reports
    recent_reports = GeneratedReport.objects.select_related(
        'user', 'upload'
    ).order_by('-generated_at')[:10]
    
    # Get most downloaded reports
    popular_reports = GeneratedReport.objects.filter(
        download_count__gt=0
    ).select_related(
        'user', 'upload'
    ).order_by('-download_count')[:10]
    
    # Get recent templates
    recent_templates = ReportTemplate.objects.select_related(
        'created_by'
    ).order_by('-created_at')[:5]
    
    context = {
        'stats': stats,
        'recent_reports': recent_reports,
        'popular_reports': popular_reports,
        'recent_templates': recent_templates,
        'title': 'Reports Dashboard',
    }
    
    return render(request, 'admin/reports/dashboard.html', context)


# ============================================================================
# URL CONFIGURATION FOR CUSTOM ADMIN VIEWS
# ============================================================================

from django.urls import path
from django.shortcuts import render

def get_admin_urls():
    """Add custom admin URLs for reports"""
    urls = [
        path('reports-dashboard/', reports_admin_dashboard, name='reports_dashboard'),
    ]
    return urls

# Uncomment to add custom URLs to admin
# admin.site.get_urls = get_admin_urls