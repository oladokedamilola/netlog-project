"""
Analytics App Admin Configuration
=================================
This module configures the Django admin interface for the analytics app models.

It provides customized admin views for managing analysis results and dashboard metrics,
with enhanced list displays, filters, search capabilities, and inline editing.
"""

from django.contrib import admin
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Avg, Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
import json
import logging

from .models import Analysis, DashboardMetric

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# ANALYSIS ADMIN
# ============================================================================

class AnalysisInline(admin.TabularInline):
    """
    Inline admin for Analysis model to display within LogUpload admin.
    
    This allows viewing analysis results directly on the LogUpload admin page.
    """
    model = Analysis
    fk_name = 'upload'
    can_delete = False
    verbose_name_plural = 'Analysis Results'
    fields = ('total_requests', 'unique_ips', 'error_rate', 'time_period_days', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    extra = 0
    max_num = 1


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    """
    Admin configuration for Analysis model.
    
    Provides comprehensive management of analysis results including
    summary metrics, security insights, and data visualization.
    """
    
    list_display = ('upload_info', 'user_info', 'total_requests', 
                   'unique_ips', 'error_rate_display', 'time_period_days', 
                   'suspicious_count', 'created_at')
    
    list_filter = ('created_at', 'updated_at', 'user__username', 
                  'upload__log_type', 'error_rate')
    
    search_fields = ('upload__filename', 'user__username', 'user__email')
    
    readonly_fields = ('created_at', 'updated_at', 'total_requests', 
                      'unique_ips', 'time_period_days', 'avg_requests_per_day',
                      'error_rate')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('upload', 'user', 'created_at', 'updated_at'),
            'classes': ('wide',),
        }),
        ('Summary Metrics', {
            'fields': ('total_requests', 'unique_ips', 'time_period_days', 
                      'avg_requests_per_day', 'error_rate'),
            'classes': ('wide',),
        }),
        ('Traffic Analysis', {
            'fields': ('hourly_distribution', 'daily_distribution'),
            'classes': ('wide', 'collapse'),
            'description': 'Time-based distribution of requests'
        }),
        ('Content Analysis', {
            'fields': ('top_endpoints', 'top_user_agents'),
            'classes': ('wide', 'collapse'),
            'description': 'Most accessed URLs and user agents'
        }),
        ('Security Insights', {
            'fields': ('suspicious_ips', 'status_codes'),
            'classes': ('wide', 'collapse'),
            'description': 'Security-related metrics and suspicious activities'
        }),
        ('IP Analysis', {
            'fields': ('top_ips',),
            'classes': ('wide', 'collapse'),
            'description': 'Top IP addresses by request count'
        }),
    )
    
    actions = ['regenerate_analysis', 'export_analysis_json', 'mark_secure']
    
    def upload_info(self, obj):
        """Display upload information with link to upload detail"""
        url = reverse('admin:logs_logupload_change', args=[obj.upload.id])
        return format_html(
            '<a href="{}">{}</a><br><small>{}</small>',
            url,
            obj.upload.filename,
            obj.upload.get_log_type_display()
        )
    upload_info.short_description = 'Log Upload'
    upload_info.admin_order_field = 'upload__filename'
    
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
    
    def error_rate_display(self, obj):
        """Display error rate with color coding"""
        if obj.error_rate < 5:
            color = 'green'
            icon = '✓'
        elif obj.error_rate < 15:
            color = 'orange'
            icon = '⚠'
        else:
            color = 'red'
            icon = '✗'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {:.1f}%</span>',
            color,
            icon,
            obj.error_rate
        )
    error_rate_display.short_description = 'Error Rate'
    error_rate_display.admin_order_field = 'error_rate'
    
    def suspicious_count(self, obj):
        """Display count of suspicious IPs with color coding"""
        count = len(obj.suspicious_ips) if obj.suspicious_ips else 0
        
        if count == 0:
            color = 'green'
        elif count < 5:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} IPs</span>',
            color,
            count
        )
    suspicious_count.short_description = 'Suspicious IPs'
    
    def regenerate_analysis(self, request, queryset):
        """Admin action to regenerate analysis for selected uploads"""
        from analytics.utils.analyzer import LogAnalyzer
        
        success_count = 0
        error_count = 0
        
        for analysis in queryset:
            try:
                upload = analysis.upload
                logger.info(f"Regenerating analysis for upload {upload.id}")
                
                # Run analysis
                analyzer = LogAnalyzer(upload)
                analysis_data = analyzer.analyze()
                
                # Update analysis object
                analysis.total_requests = analysis_data['total_requests']
                analysis.unique_ips = analysis_data['unique_ips']
                analysis.time_period_days = analysis_data['time_period_days']
                analysis.avg_requests_per_day = analysis_data['avg_requests_per_day']
                analysis.top_ips = analysis_data['top_ips']
                analysis.status_codes = analysis_data['status_codes']
                analysis.top_endpoints = analysis_data['top_endpoints']
                analysis.top_user_agents = analysis_data['top_user_agents']
                analysis.hourly_distribution = analysis_data['hourly_distribution']
                analysis.daily_distribution = analysis_data['daily_distribution']
                analysis.suspicious_ips = analysis_data['suspicious_ips']
                analysis.error_rate = analysis_data['error_rate']
                analysis.save()
                
                success_count += 1
                logger.info(f"Successfully regenerated analysis for upload {upload.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to regenerate analysis for upload {analysis.upload.id}: {str(e)}")
        
        self.message_user(
            request,
            f"Regenerated {success_count} analysis(es). Failed: {error_count}"
        )
    regenerate_analysis.short_description = "Regenerate selected analyses"
    
    def export_analysis_json(self, request, queryset):
        """Admin action to export analysis as JSON"""
        import json
        from django.http import JsonResponse
        
        data = []
        for analysis in queryset:
            analysis_data = {
                'upload': analysis.upload.filename,
                'user': analysis.user.username,
                'created_at': analysis.created_at.isoformat(),
                'total_requests': analysis.total_requests,
                'unique_ips': analysis.unique_ips,
                'time_period_days': analysis.time_period_days,
                'avg_requests_per_day': analysis.avg_requests_per_day,
                'top_ips': analysis.top_ips,
                'status_codes': analysis.status_codes,
                'top_endpoints': analysis.top_endpoints,
                'top_user_agents': analysis.top_user_agents,
                'hourly_distribution': analysis.hourly_distribution,
                'daily_distribution': analysis.daily_distribution,
                'suspicious_ips': analysis.suspicious_ips,
                'error_rate': analysis.error_rate,
            }
            data.append(analysis_data)
        
        # Create JSON response
        response = JsonResponse(data, safe=False)
        response['Content-Disposition'] = 'attachment; filename="analyses_export.json"'
        
        logger.info(f"Admin {request.user.username} exported {len(data)} analyses to JSON")
        return response
    export_analysis_json.short_description = "Export selected as JSON"
    
    def mark_secure(self, request, queryset):
        """Admin action to clear suspicious IPs (mark as secure)"""
        updated = 0
        for analysis in queryset:
            if analysis.suspicious_ips:
                analysis.suspicious_ips = []
                analysis.save()
                updated += 1
        
        self.message_user(request, f"Cleared suspicious IPs for {updated} analysis(es)")
        logger.info(f"Admin {request.user.username} cleared suspicious IPs for {updated} analyses")
    mark_secure.short_description = "Clear suspicious IPs"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('upload', 'user')
    
    class Media:
        """Add custom CSS for admin styling"""
        css = {
            'all': ('admin/css/analytics_admin.css',)
        }


# ============================================================================
# DASHBOARD METRICS ADMIN
# ============================================================================

@admin.register(DashboardMetric)
class DashboardMetricAdmin(admin.ModelAdmin):
    """
    Admin configuration for DashboardMetric model.
    
    Provides monitoring of user dashboard metrics including
    upload activity and request analysis statistics.
    """
    
    list_display = ('user', 'metric_date', 'total_uploads', 
                   'total_requests_analyzed', 'avg_requests_per_upload',
                   'last_upload_activity', 'data_quality')
    
    list_filter = ('metric_date', 'user__username', 'total_uploads')
    
    search_fields = ('user__username', 'user__email')
    
    readonly_fields = ('metric_date', 'total_uploads', 'total_requests_analyzed',
                      'avg_requests_per_upload', 'last_upload_date')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'metric_date'),
            'classes': ('wide',),
        }),
        ('Upload Metrics', {
            'fields': ('total_uploads', 'last_upload_date'),
            'classes': ('wide',),
        }),
        ('Request Metrics', {
            'fields': ('total_requests_analyzed', 'avg_requests_per_upload'),
            'classes': ('wide',),
        }),
    )
    
    actions = ['refresh_metrics', 'export_metrics_csv']
    
    def last_upload_activity(self, obj):
        """Display last upload activity with relative time"""
        if obj.last_upload_date:
            time_diff = timezone.now() - obj.last_upload_date
            days = time_diff.days
            hours = time_diff.seconds // 3600
            
            if days > 0:
                return f"{days} day(s) ago"
            elif hours > 0:
                return f"{hours} hour(s) ago"
            else:
                return "Today"
        return "No uploads"
    last_upload_activity.short_description = 'Last Activity'
    
    def data_quality(self, obj):
        """Display data quality indicator based on metrics"""
        if obj.total_uploads == 0:
            return format_html('<span style="color: gray;">No data</span>')
        
        if obj.avg_requests_per_upload > 1000:
            quality = "Excellent"
            color = "green"
        elif obj.avg_requests_per_upload > 500:
            quality = "Good"
            color = "blue"
        elif obj.avg_requests_per_upload > 100:
            quality = "Average"
            color = "orange"
        else:
            quality = "Low"
            color = "red"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            quality
        )
    data_quality.short_description = 'Data Quality'
    
    def refresh_metrics(self, request, queryset):
        """Admin action to refresh metrics for selected users"""
        from logs.models import LogUpload, ParsedEntry
        
        updated = 0
        for metric in queryset:
            user = metric.user
            
            # Calculate fresh metrics
            uploads = LogUpload.objects.filter(user=user)
            total_uploads = uploads.count()
            
            if total_uploads > 0:
                total_requests = ParsedEntry.objects.filter(upload__in=uploads).count()
                avg_requests = total_requests / total_uploads
                last_upload = uploads.order_by('-uploaded_at').first().uploaded_at
            else:
                total_requests = 0
                avg_requests = 0
                last_upload = None
            
            # Update metric
            metric.total_uploads = total_uploads
            metric.total_requests_analyzed = total_requests
            metric.avg_requests_per_upload = avg_requests
            metric.last_upload_date = last_upload
            metric.save()
            
            updated += 1
        
        self.message_user(request, f"Refreshed metrics for {updated} records")
        logger.info(f"Admin {request.user.username} refreshed {updated} dashboard metrics")
    refresh_metrics.short_description = "Refresh selected metrics"
    
    def export_metrics_csv(self, request, queryset):
        """Admin action to export metrics as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="dashboard_metrics.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'User', 'Email', 'Metric Date', 'Total Uploads', 
            'Total Requests', 'Avg Requests/Upload', 'Last Upload'
        ])
        
        for metric in queryset:
            writer.writerow([
                metric.user.username,
                metric.user.email,
                metric.metric_date,
                metric.total_uploads,
                metric.total_requests_analyzed,
                round(metric.avg_requests_per_upload, 2),
                metric.last_upload_date
            ])
        
        logger.info(f"Admin {request.user.username} exported {queryset.count()} metrics to CSV")
        return response
    export_metrics_csv.short_description = "Export selected as CSV"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')


# ============================================================================
# CUSTOM ADMIN VIEWS AND DASHBOARD
# ============================================================================

class AnalyticsDashboard:
    """
    Helper class for analytics dashboard statistics.
    Can be used in custom admin templates.
    """
    
    @staticmethod
    def get_stats():
        """Get summary statistics for analytics dashboard"""
        from django.contrib.auth.models import User
        from logs.models import LogUpload, ParsedEntry
        
        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)
        last_7d = now - timezone.timedelta(days=7)
        last_30d = now - timezone.timedelta(days=30)
        
        # Analysis statistics
        total_analyses = Analysis.objects.count()
        analyses_today = Analysis.objects.filter(created_at__gte=last_24h).count()
        analyses_week = Analysis.objects.filter(created_at__gte=last_7d).count()
        analyses_month = Analysis.objects.filter(created_at__gte=last_30d).count()
        
        # Request statistics
        total_requests = ParsedEntry.objects.count()
        requests_today = ParsedEntry.objects.filter(timestamp__gte=last_24h).count()
        
        # Error statistics
        high_error_analyses = Analysis.objects.filter(error_rate__gt=20).count()
        
        # Suspicious activity
        analyses_with_suspicious = Analysis.objects.exclude(
            suspicious_ips=[]
        ).exclude(suspicious_ips__isnull=True).count()
        
        # Top users by activity
        top_users = User.objects.annotate(
            analysis_count=Count('analyses'),
            total_requests=Sum('analyses__total_requests')
        ).order_by('-total_requests')[:5]
        
        stats = {
            'total_analyses': total_analyses,
            'analyses_today': analyses_today,
            'analyses_week': analyses_week,
            'analyses_month': analyses_month,
            'total_requests': total_requests,
            'requests_today': requests_today,
            'high_error_analyses': high_error_analyses,
            'analyses_with_suspicious': analyses_with_suspicious,
            'avg_error_rate': Analysis.objects.aggregate(
                avg_rate=models.Avg('error_rate')
            )['avg_rate'] or 0,
            'top_users': top_users,
        }
        
        # Calculate averages
        if total_analyses > 0:
            stats['avg_requests_per_analysis'] = round(
                total_requests / total_analyses, 1
            )
        else:
            stats['avg_requests_per_analysis'] = 0
        
        return stats


@staff_member_required
def analytics_admin_dashboard(request):
    """
    Custom admin dashboard view for analytics statistics.
    """
    stats = AnalyticsDashboard.get_stats()
    
    # Get recent analyses with high error rates
    recent_high_errors = Analysis.objects.filter(
        error_rate__gt=20
    ).select_related('upload', 'user').order_by('-created_at')[:10]
    
    # Get recent suspicious activities
    recent_suspicious = Analysis.objects.exclude(
        suspicious_ips=[]
    ).exclude(
        suspicious_ips__isnull=True
    ).select_related('upload', 'user').order_by('-created_at')[:10]
    
    # Get activity timeline (last 7 days)
    from django.db.models import Count, DateField
    from django.db.models.functions import TruncDate
    
    last_7_days = timezone.now() - timezone.timedelta(days=7)
    timeline = Analysis.objects.filter(
        created_at__gte=last_7_days
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    context = {
        'stats': stats,
        'recent_high_errors': recent_high_errors,
        'recent_suspicious': recent_suspicious,
        'timeline': timeline,
        'title': 'Analytics Dashboard',
    }
    
    return render(request, 'admin/analytics/dashboard.html', context)


# ============================================================================
# URL CONFIGURATION FOR CUSTOM ADMIN VIEWS
# ============================================================================

from django.urls import path
from django.shortcuts import render

def get_admin_urls():
    """Add custom admin URLs for analytics"""
    urls = [
        path('analytics-dashboard/', 
             analytics_admin_dashboard, 
             name='analytics_dashboard'),
    ]
    return urls

# Uncomment to add custom URLs to admin
# admin.site.get_urls = get_admin_urls


# ============================================================================
# REGISTER ANY ADDITIONAL ADMIN VIEWS
# ============================================================================

# Optional: Add model admins for any other models that might be added later
# @admin.register(SomeOtherModel)
# class SomeOtherModelAdmin(admin.ModelAdmin):
#     pass