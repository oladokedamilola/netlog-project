# analytics/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import json
import logging

from logs.models import LogUpload, ParsedEntry
from .models import Analysis
from .utils.analyzer import LogAnalyzer

logger = logging.getLogger(__name__)

# Helper functions (no self parameter)
def _prepare_hourly_chart_data(hourly_distribution):
    """Format hourly distribution for chart.js"""
    chart_data = []
    for hour, count in enumerate(hourly_distribution):
        chart_data.append({
            'hour': f"{hour:02d}:00",
            'count': count
        })
    return json.dumps(chart_data)

def _prepare_daily_chart_data(daily_distribution):
    """Format daily distribution for chart.js"""
    chart_data = []
    for date_str, count in daily_distribution.items():
        chart_data.append({
            'day': date_str,
            'count': count
        })
    return json.dumps(chart_data)

def _prepare_status_codes_data(status_codes):
    """Format status codes for chart.js"""
    chart_data = []
    for status, count in status_codes.items():
        chart_data.append({
            'status_code': status,
            'count': count
        })
    return json.dumps(chart_data)

def _prepare_top_ips_data(top_ips, suspicious_ips):
    """Format top IPs for table"""
    suspicious_ip_list = [ip['ip'] for ip in suspicious_ips]
    table_data = []
    for ip, count in list(top_ips.items())[:20]:  # Top 20 IPs
        table_data.append({
            'ip_address': ip,
            'requests_count': count,
            'suspicious': ip in suspicious_ip_list
        })
    return table_data

def _prepare_endpoints_data(top_endpoints, upload):
    """Format endpoints for table with error counts"""
    table_data = []
    for url, count in list(top_endpoints.items())[:20]:  # Top 20 endpoints
        # Calculate error count for this endpoint
        error_count = ParsedEntry.objects.filter(
            upload=upload,
            url=url,
            status_code__gte=400,
            status_code__lt=600
        ).count()
        
        # Truncate long URLs for display
        display_url = url[:100] + "..." if len(url) > 100 else url
        table_data.append({
            'url': display_url,
            'full_url': url,
            'requests_count': count,
            'error_count': error_count
        })
    return table_data

def _calculate_total_errors(status_codes):
    """Calculate total error count from status codes"""
    error_codes = ['4xx', '5xx']
    total_errors = 0
    for code in error_codes:
        total_errors += status_codes.get(code, 0)
    return total_errors

def _get_current_window_errors(upload):
    """Get errors in current time window (last 24 hours)"""
    current_window = timezone.now() - timedelta(days=1)
    return ParsedEntry.objects.filter(
        upload=upload,
        status_code__gte=400,
        status_code__lt=600,
        timestamp__gte=current_window
    ).count()

def _get_previous_window_errors(upload):
    """Get errors in previous time window (24-48 hours ago)"""
    end_window = timezone.now() - timedelta(days=1)
    start_window = end_window - timedelta(days=1)
    return ParsedEntry.objects.filter(
        upload=upload,
        status_code__gte=400,
        status_code__lt=600,
        timestamp__range=(start_window, end_window)
    ).count()

def _calculate_percent_change(current, previous):
    """Calculate percentage change in errors"""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    
    return ((current - previous) / previous) * 100

@login_required
def analytics_view(request, upload_id):
    """
    Single-page analytics view for a specific log upload
    """
    # Get the upload
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    
    # Get or create analysis
    analysis, created = Analysis.objects.get_or_create(
        upload=upload,
        defaults={'user': request.user}
    )
    
    # Analyze if new or refresh requested
    if created or request.GET.get('refresh'):
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
    
    # Get parsed entries for the table
    entries = ParsedEntry.objects.filter(upload=upload).order_by('-timestamp')[:100]  # Last 100 entries
    
    # Calculate error metrics
    current_errors = _get_current_window_errors(upload)
    previous_errors = _get_previous_window_errors(upload)
    percent_change = _calculate_percent_change(current_errors, previous_errors)
    
    # Prepare context data
    context = {
        'upload': upload,
        'analysis': analysis,
        'entries': entries,
        
        # Chart data
        'hourly_chart': _prepare_hourly_chart_data(analysis.hourly_distribution),
        'daily_chart': _prepare_daily_chart_data(analysis.daily_distribution),
        'status_codes': _prepare_status_codes_data(analysis.status_codes),
        'top_ips': _prepare_top_ips_data(analysis.top_ips, analysis.suspicious_ips),
        'endpoints': _prepare_endpoints_data(analysis.top_endpoints, upload),
        
        # Summary stats
        'total_requests': analysis.total_requests,
        'parsed_entries': entries.count(),
        'total_errors': _calculate_total_errors(analysis.status_codes),
        'current_errors': current_errors,
        'previous_errors': previous_errors,
        'percent_change': percent_change,
    }
    
    return render(request, 'analytics/analytics.html', context)

@login_required
def chart_data_api(request, upload_id):
    """
    API endpoint for chart data (optional, for dynamic updates)
    """
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    analysis = get_object_or_404(Analysis, upload=upload)
    
    chart_type = request.GET.get('type', 'overview')
    
    if chart_type == 'hourly':
        data = {
            'labels': [f"{hour:02d}:00" for hour in range(24)],
            'datasets': [{
                'label': 'Requests per hour',
                'data': analysis.hourly_distribution,
                'borderColor': 'rgb(255, 122, 0)',  # Orange to match your theme
                'backgroundColor': 'rgba(255, 122, 0, 0.2)',
                'tension': 0.2
            }]
        }
    elif chart_type == 'daily':
        # Convert daily distribution to arrays
        labels = list(analysis.daily_distribution.keys())
        values = list(analysis.daily_distribution.values())
        data = {
            'labels': labels,
            'datasets': [{
                'label': 'Requests per day',
                'data': values,
                'backgroundColor': '#1A1F36'  # Dark blue from your theme
            }]
        }
    elif chart_type == 'status':
        labels = list(analysis.status_codes.keys())
        values = list(analysis.status_codes.values())
        data = {
            'labels': labels,
            'datasets': [{
                'label': 'Status Codes',
                'data': values,
                'backgroundColor': ['#FF7A00', '#1A1F36', '#FFF4E6', '#FF7A00', '#1A1F36']
            }]
        }
    else:  # overview stats
        data = {
            'total_requests': analysis.total_requests,
            'unique_ips': analysis.unique_ips,
            'error_rate': round(analysis.error_rate, 2),
            'time_period': round(analysis.time_period_days, 1),
            'avg_daily': round(analysis.avg_requests_per_day, 1)
        }
    
    return JsonResponse(data)