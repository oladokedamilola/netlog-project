"""
Analytics App Views
==================
This module handles all analytics-related views including the main analytics dashboard,
detailed log analysis, and API endpoints for chart data.

Each view includes proper logging for monitoring and debugging purposes.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from datetime import timedelta, datetime
from collections import defaultdict, Counter
import json
import logging

# Local application imports
from logs.models import LogUpload, ParsedEntry
from .models import Analysis
from .utils.analyzer import LogAnalyzer

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# MAIN ANALYTICS DASHBOARD VIEWS
# ============================================================================

@login_required
def analytics_dashboard(request):
    """
    Main analytics dashboard showing overview of all user's log data.
    
    This view:
    1. Fetches all user uploads within specified date range
    2. Calculates key metrics (total requests, unique IPs, error rates)
    3. Prepares chart data for visualizations
    4. Generates intelligent recommendations based on data patterns
    5. Identifies suspicious IPs from analysis results
    
    Template: analytics/dashboard.html
    
    Query Parameters:
        range: Date range (days number or 'custom')
        start: Custom start date (YYYY-MM-DD)
        end: Custom end date (YYYY-MM-DD)
    """
    logger.info("=" * 50)
    logger.info("ANALYTICS DASHBOARD VIEW CALLED")
    logger.info("=" * 50)
    
    user = request.user
    logger.info(f"User: {user.username}")
    
    today = timezone.now().date()
    
    # Get date range from request (default to last 30 days)
    date_range = request.GET.get('range', '30')
    logger.info(f"Date range parameter: {date_range}")
    
    # Parse date range parameters
    if date_range == 'custom':
        start_date_str = request.GET.get('start', (today - timedelta(days=30)).isoformat())
        end_date_str = request.GET.get('end', today.isoformat())
        logger.info(f"Custom date range - Start: {start_date_str}, End: {end_date_str}")
        
        # Parse strings to datetime
        start_date = timezone.make_aware(datetime.fromisoformat(start_date_str))
        end_date = timezone.make_aware(datetime.fromisoformat(end_date_str)) + timedelta(days=1)
        
        # For date objects (used in loop)
        start_date_obj = start_date.date()
        end_date_obj = end_date.date()
    else:
        days = int(date_range)
        logger.info(f"Standard date range - Last {days} days")
        start_date_obj = today - timedelta(days=days)
        end_date_obj = today + timedelta(days=1)
        
        # Convert to datetime for queryset
        start_date = timezone.make_aware(datetime.combine(start_date_obj, datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(end_date_obj, datetime.min.time()))
    
    logger.info(f"Query date range: {start_date} to {end_date}")
    
    # Get all user uploads in date range
    uploads = LogUpload.objects.filter(
        user=user,
        uploaded_at__gte=start_date,
        uploaded_at__lte=end_date
    ).order_by('-uploaded_at')
    
    logger.info(f"Found {uploads.count()} uploads in date range")
    
    # Get all parsed entries for these uploads
    entries = ParsedEntry.objects.filter(upload__in=uploads)
    total_entries = entries.count()
    logger.info(f"Found {total_entries} parsed entries")
    
    # ========================================================================
    # Key Metrics Calculation
    # ========================================================================
    
    total_requests = total_entries
    total_uploads = uploads.count()
    unique_ips = entries.values('ip_address').distinct().count()
    logger.info(f"Key metrics - Requests: {total_requests}, Uploads: {total_uploads}, Unique IPs: {unique_ips}")
    
    # Error rate
    error_count = entries.filter(status_code__gte=400).count()
    error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
    logger.info(f"Error metrics - Count: {error_count}, Rate: {error_rate:.2f}%")
    
    # ========================================================================
    # Time Series Data for Charts
    # ========================================================================
    
    daily_data = defaultdict(int)
    hourly_data = defaultdict(int)
    
    for entry in entries:
        if entry.timestamp:  # Add null check
            date_key = entry.timestamp.date().isoformat()
            daily_data[date_key] += 1
            hourly_data[entry.timestamp.hour] += 1
    
    # Fill in missing dates
    current = start_date_obj
    end = end_date_obj
    while current <= end:
        if current.isoformat() not in daily_data:
            daily_data[current.isoformat()] = 0
        current += timedelta(days=1)
    
    # Sort daily data
    daily_labels = sorted(daily_data.keys())
    daily_values = [daily_data[date] for date in daily_labels]
    logger.info(f"Daily data prepared - {len(daily_labels)} days")
    
    # ========================================================================
    # Status Code Distribution
    # ========================================================================
    
    status_codes = {
        '2xx': entries.filter(status_code__gte=200, status_code__lt=300).count(),
        '3xx': entries.filter(status_code__gte=300, status_code__lt=400).count(),
        '4xx': entries.filter(status_code__gte=400, status_code__lt=500).count(),
        '5xx': entries.filter(status_code__gte=500, status_code__lt=600).count(),
    }
    logger.info(f"Status code distribution: {status_codes}")
    
    # ========================================================================
    # Top Endpoints and IPs
    # ========================================================================
    
    # Top endpoints
    top_endpoints = entries.values('url').annotate(
        count=Count('url')
    ).exclude(url__isnull=True).exclude(url='').order_by('-count')[:10]
    logger.info(f"Top 10 endpoints retrieved")
    
    # Top IPs
    top_ips = entries.values('ip_address').annotate(
        count=Count('ip_address')
    ).order_by('-count')[:10]
    logger.info(f"Top 10 IPs retrieved")
    
    # ========================================================================
    # Suspicious IPs from Analysis Models
    # ========================================================================
    
    suspicious_ips = []
    for upload in uploads:
        try:
            analysis = Analysis.objects.get(upload=upload)
            if analysis.suspicious_ips:
                # Handle both list of dicts and list of strings
                if analysis.suspicious_ips and isinstance(analysis.suspicious_ips, list):
                    for ip_data in analysis.suspicious_ips:
                        if isinstance(ip_data, dict):
                            suspicious_ips.append(ip_data.get('ip', str(ip_data)))
                        else:
                            suspicious_ips.append(str(ip_data))
        except Analysis.DoesNotExist:
            continue
    
    logger.info(f"Found {len(suspicious_ips)} suspicious IPs across uploads")
    
    # ========================================================================
    # Recent Uploads with Stats
    # ========================================================================
    
    recent_uploads = []
    for upload in uploads[:5]:
        upload.entries_count = upload.entries.count()
        upload.error_count = upload.entries.filter(status_code__gte=400).count()
        recent_uploads.append(upload)
    logger.info(f"Prepared {len(recent_uploads)} recent uploads with stats")
    
    # ========================================================================
    # Peak Hours Analysis
    # ========================================================================
    
    peak_hours = sorted(
        [(hour, count) for hour, count in hourly_data.items()],
        key=lambda x: x[1],
        reverse=True
    )[:3]
    logger.info(f"Peak hours identified: {peak_hours}")
    
    # ========================================================================
    # Generate Intelligent Recommendations
    # ========================================================================
    
    recommendations = []
    logger.info("Generating recommendations based on data patterns")
    
    # Check for high error rate
    if error_rate > 10:
        logger.info(f"High error rate detected: {error_rate:.1f}%")
        recommendations.append({
            'type': 'warning',
            'icon': 'fa-exclamation-triangle',
            'title': 'High Error Rate Detected',
            'message': f'Your error rate is {error_rate:.1f}%. Consider investigating the most frequent 4xx/5xx responses.',
            'action': 'View Details',
            'link': '#'
        })
    
    # Check for traffic spikes
    if daily_values and len(daily_values) > 1:
        avg = sum(daily_values) / len(daily_values)
        max_val = max(daily_values)
        if max_val > avg * 2:
            max_date = daily_labels[daily_values.index(max_val)]
            logger.info(f"Traffic spike detected on {max_date}: {max_val} requests (avg: {avg:.1f})")
            recommendations.append({
                'type': 'info',
                'icon': 'fa-chart-line',
                'title': 'Traffic Spike Detected',
                'message': f'Unusual traffic spike on {max_date} with {max_val} requests ({(max_val/avg-1)*100:.0f}% above average).',
                'action': 'Analyze',
                'link': '#'
            })
    
    # Check for security concerns
    if len(suspicious_ips) > 5:
        logger.info(f"Multiple suspicious IPs detected: {len(suspicious_ips)}")
        recommendations.append({
            'type': 'danger',
            'icon': 'fa-shield-alt',
            'title': 'Multiple Suspicious IPs',
            'message': f'{len(suspicious_ips)} potentially malicious IPs detected. Review security insights.',
            'action': 'Review',
            'link': '#'
        })
    
    logger.info(f"Generated {len(recommendations)} recommendations")
    
    # ========================================================================
    # Prepare Context
    # ========================================================================
    
    context = {
        'page_title': 'Analytics Dashboard',
        'total_requests': total_requests,
        'total_uploads': total_uploads,
        'unique_ips': unique_ips,
        'error_rate': round(error_rate, 1),
        'total_errors': error_count,
        'daily_labels': json.dumps(daily_labels),
        'daily_values': json.dumps(daily_values),
        'status_codes': status_codes,
        'top_endpoints': top_endpoints,
        'top_ips': top_ips,
        'suspicious_ips': suspicious_ips[:10],
        'recent_uploads': recent_uploads,
        'peak_hours': peak_hours,
        'hourly_data': json.dumps([hourly_data.get(i, 0) for i in range(24)]),
        'recommendations': recommendations,
        'date_range': date_range,
        'start_date': start_date_obj.isoformat() if date_range == 'custom' else None,
        'end_date': end_date_obj.isoformat() if date_range == 'custom' else None,
    }
    
    logger.info("Rendering analytics dashboard template")
    return render(request, 'analytics/dashboard.html', context)


@login_required
def dashboard_chart_data(request):
    """
    API endpoint for dashboard chart data (for dynamic updates).
    
    This view:
    1. Returns JSON data for charts based on request parameters
    2. Supports daily, hourly, and status code charts
    3. Used by frontend for dynamic updates without page reload
    
    Query Parameters:
        type: Chart type ('daily', 'hourly', 'status')
        range: Date range (days number or 'custom')
        start: Custom start date (for custom range)
        end: Custom end date (for custom range)
    
    Returns: JsonResponse with chart data formatted for Chart.js
    """
    logger.info("=" * 50)
    logger.info("DASHBOARD CHART DATA API CALLED")
    logger.info("=" * 50)
    
    user = request.user
    chart_type = request.GET.get('type', 'daily')
    date_range = request.GET.get('range', '30')
    
    logger.info(f"Request parameters - User: {user.username}, Chart type: {chart_type}, Range: {date_range}")
    
    today = timezone.now().date()
    
    # Parse date range
    if date_range == 'custom':
        start_date_str = request.GET.get('start', (today - timedelta(days=30)).isoformat())
        end_date_str = request.GET.get('end', today.isoformat())
        logger.info(f"Custom range - Start: {start_date_str}, End: {end_date_str}")
        
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str) + timedelta(days=1)
    else:
        days = int(date_range)
        logger.info(f"Standard range - Last {days} days")
        start_date = today - timedelta(days=days)
        end_date = today + timedelta(days=1)
    
    # Get uploads and entries
    uploads = LogUpload.objects.filter(
        user=user,
        uploaded_at__gte=start_date,
        uploaded_at__lte=end_date
    )
    logger.info(f"Found {uploads.count()} uploads in date range")
    
    entries = ParsedEntry.objects.filter(upload__in=uploads)
    logger.info(f"Found {entries.count()} entries")
    
    # ========================================================================
    # Generate Chart Data Based on Type
    # ========================================================================
    
    if chart_type == 'daily':
        logger.info("Generating daily chart data")
        daily_data = defaultdict(int)
        for entry in entries:
            if entry.timestamp:
                date_key = entry.timestamp.date().isoformat()
                daily_data[date_key] += 1
        
        # Fill in missing dates
        current = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date
        
        while current <= end:
            if current.isoformat() not in daily_data:
                daily_data[current.isoformat()] = 0
            current += timedelta(days=1)
        
        labels = sorted(daily_data.keys())
        values = [daily_data[date] for date in labels]
        
        data = {
            'labels': labels,
            'datasets': [{
                'label': 'Requests',
                'data': values,
                'backgroundColor': '#FF7A00',
                'borderColor': '#FF7A00',
                'borderWidth': 1
            }]
        }
        logger.info(f"Daily chart data prepared - {len(labels)} days")
    
    elif chart_type == 'hourly':
        logger.info("Generating hourly chart data")
        hourly_data = [0] * 24
        for entry in entries:
            if entry.timestamp:
                hourly_data[entry.timestamp.hour] += 1
        
        data = {
            'labels': [f"{i:02d}:00" for i in range(24)],
            'datasets': [{
                'label': 'Requests',
                'data': hourly_data,
                'backgroundColor': '#1A1F36',
                'borderColor': '#1A1F36',
                'borderWidth': 1
            }]
        }
        logger.info("Hourly chart data prepared")
    
    elif chart_type == 'status':
        logger.info("Generating status code chart data")
        status_data = {
            '2xx': entries.filter(status_code__gte=200, status_code__lt=300).count(),
            '3xx': entries.filter(status_code__gte=300, status_code__lt=400).count(),
            '4xx': entries.filter(status_code__gte=400, status_code__lt=500).count(),
            '5xx': entries.filter(status_code__gte=500, status_code__lt=600).count(),
        }
        logger.info(f"Status counts: {status_data}")
        
        data = {
            'labels': list(status_data.keys()),
            'datasets': [{
                'data': list(status_data.values()),
                'backgroundColor': ['#16a34a', '#f59e0b', '#FF7A00', '#dc3545'],
                'borderWidth': 0
            }]
        }
    
    logger.info("Returning chart data JSON response")
    return JsonResponse(data)


# ============================================================================
# DETAILED ANALYTICS VIEWS (Single Log Upload)
# ============================================================================

@login_required
def analytics_view(request, upload_id):
    """
    Single-page analytics view for a specific log upload.
    
    This view:
    1. Retrieves a specific log upload
    2. Gets or creates analysis for that upload
    3. Performs analysis if needed or refresh requested
    4. Prepares all chart data and statistics for display
    
    Args:
        upload_id: ID of the LogUpload to analyze
        
    Template: analytics/analytics.html
    
    Query Parameters:
        refresh: If present, forces re-analysis of the log
    """
    logger.info("=" * 50)
    logger.info("DETAILED ANALYTICS VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"Upload ID: {upload_id}")
    
    # Get the upload
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    logger.info(f"Upload found: {upload.file.name if upload.file else 'No file'}")
    logger.info(f"Upload status: {upload.status}")
    
    # Get or create analysis
    analysis, created = Analysis.objects.get_or_create(
        upload=upload,
        defaults={'user': request.user}
    )
    
    if created:
        logger.info(f"Created new analysis for upload {upload_id}")
    else:
        logger.info(f"Retrieved existing analysis for upload {upload_id}")
    
    # Analyze if new or refresh requested
    refresh_requested = request.GET.get('refresh', False)
    if created or refresh_requested:
        if refresh_requested:
            logger.info("Refresh requested, re-analyzing log")
        
        logger.info("Starting log analysis")
        analyzer = LogAnalyzer(upload)
        analysis_data = analyzer.analyze()
        logger.info("Analysis completed successfully")
        
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
        logger.info("Analysis data saved to database")
    
    # Get parsed entries for the table
    entries = ParsedEntry.objects.filter(upload=upload).order_by('-timestamp')[:100]  # Last 100 entries
    logger.info(f"Retrieved {entries.count()} recent entries for display")
    
    # Calculate error metrics
    current_errors = _get_current_window_errors(upload)
    previous_errors = _get_previous_window_errors(upload)
    percent_change = _calculate_percent_change(current_errors, previous_errors)
    logger.info(f"Error metrics - Current: {current_errors}, Previous: {previous_errors}, Change: {percent_change:.1f}%")
    
    # Get first and last dates from daily_distribution
    first_date = 'N/A'
    last_date = 'N/A'
    if analysis.daily_distribution and isinstance(analysis.daily_distribution, dict):
        keys = list(analysis.daily_distribution.keys())
        if keys:
            first_date = keys[0]
            last_date = keys[-1]
            logger.info(f"Date range in data: {first_date} to {last_date}")
    
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
        
        # First and last dates - use these directly in template
        'first_date': first_date,
        'last_date': last_date,
    }
    
    logger.info("Rendering detailed analytics template")
    return render(request, 'analytics/analytics.html', context)


@login_required
def chart_data_api(request, upload_id):
    """
    API endpoint for chart data (optional, for dynamic updates).
    
    This view:
    1. Returns JSON data for charts on the detailed analytics page
    2. Supports hourly, daily, status, and overview data types
    
    Args:
        upload_id: ID of the LogUpload to get chart data for
        
    Query Parameters:
        type: Chart type ('hourly', 'daily', 'status', or default overview)
    
    Returns: JsonResponse with chart data formatted for Chart.js
    """
    logger.info("=" * 50)
    logger.info("CHART DATA API CALLED")
    logger.info("=" * 50)
    logger.info(f"Upload ID: {upload_id}")
    
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    analysis = get_object_or_404(Analysis, upload=upload)
    logger.info(f"Found analysis for upload {upload_id}")
    
    chart_type = request.GET.get('type', 'overview')
    logger.info(f"Chart type requested: {chart_type}")
    
    # ========================================================================
    # Generate Chart Data Based on Type
    # ========================================================================
    
    if chart_type == 'hourly':
        logger.info("Generating hourly chart data")
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
        logger.info("Generating daily chart data")
        # Convert daily distribution to arrays
        labels = list(analysis.daily_distribution.keys())
        values = list(analysis.daily_distribution.values())
        logger.info(f"Daily data - {len(labels)} days, range: {labels[0] if labels else 'N/A'} to {labels[-1] if labels else 'N/A'}")
        
        data = {
            'labels': labels,
            'datasets': [{
                'label': 'Requests per day',
                'data': values,
                'backgroundColor': '#1A1F36'  # Dark blue from your theme
            }]
        }
        
    elif chart_type == 'status':
        logger.info("Generating status code chart data")
        labels = list(analysis.status_codes.keys())
        values = list(analysis.status_codes.values())
        logger.info(f"Status data: {dict(zip(labels, values))}")
        
        data = {
            'labels': labels,
            'datasets': [{
                'label': 'Status Codes',
                'data': values,
                'backgroundColor': ['#FF7A00', '#1A1F36', '#FFF4E6', '#FF7A00', '#1A1F36']
            }]
        }
        
    else:  # overview stats
        logger.info("Generating overview stats")
        data = {
            'total_requests': analysis.total_requests,
            'unique_ips': analysis.unique_ips,
            'error_rate': round(analysis.error_rate, 2),
            'time_period': round(analysis.time_period_days, 1),
            'avg_daily': round(analysis.avg_requests_per_day, 1)
        }
    
    logger.info("Returning chart data JSON response")
    return JsonResponse(data)


@login_required
def check_processing_status(request, upload_id):
    """
    API endpoint to check if processing is complete.
    
    This view:
    1. Checks the status of a log upload
    2. Determines if analysis exists
    3. Used by frontend to poll for completion
    
    Args:
        upload_id: ID of the LogUpload to check
        
    Returns: JsonResponse with status information
    """
    logger.info("=" * 50)
    logger.info("CHECK PROCESSING STATUS API CALLED")
    logger.info("=" * 50)
    logger.info(f"Upload ID: {upload_id}")
    
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    logger.info(f"Upload status: {upload.status}")
    
    # Check if analysis exists
    has_analysis = Analysis.objects.filter(upload=upload).exists()
    logger.info(f"Has analysis: {has_analysis}")
    
    response_data = {
        'status': upload.status,
        'has_analysis': has_analysis,
        'processed_at': upload.processed_at,
        'error_message': upload.error_message if upload.status == 'failed' else None
    }
    
    logger.info(f"Returning status response: {response_data}")
    return JsonResponse(response_data)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _prepare_hourly_chart_data(hourly_distribution):
    """
    Format hourly distribution for chart.js.
    
    Args:
        hourly_distribution: List of 24 integers representing requests per hour
        
    Returns: JSON string of formatted chart data
    """
    logger.debug(f"Preparing hourly chart data from distribution of length {len(hourly_distribution) if hourly_distribution else 0}")
    chart_data = []
    for hour, count in enumerate(hourly_distribution):
        chart_data.append({
            'hour': f"{hour:02d}:00",
            'count': count
        })
    return json.dumps(chart_data)


def _prepare_daily_chart_data(daily_distribution):
    """
    Format daily distribution for chart.js.
    
    Args:
        daily_distribution: Dictionary mapping dates to request counts
        
    Returns: JSON string of formatted chart data
    """
    logger.debug(f"Preparing daily chart data from distribution with {len(daily_distribution) if daily_distribution else 0} entries")
    chart_data = []
    for date_str, count in daily_distribution.items():
        chart_data.append({
            'day': date_str,
            'count': count
        })
    return json.dumps(chart_data)


def _prepare_status_codes_data(status_codes):
    """
    Format status codes for chart.js.
    
    Args:
        status_codes: Dictionary of status code categories and counts
        
    Returns: JSON string of formatted chart data
    """
    logger.debug(f"Preparing status codes chart data: {status_codes}")
    chart_data = []
    for status, count in status_codes.items():
        chart_data.append({
            'status_code': status,
            'count': count
        })
    return json.dumps(chart_data)


def _prepare_top_ips_data(top_ips, suspicious_ips):
    """
    Format top IPs for table display.
    
    Args:
        top_ips: Dictionary of IP addresses and request counts
        suspicious_ips: List of suspicious IP addresses
        
    Returns: List of formatted IP data with suspicious flags
    """
    logger.debug(f"Preparing top IPs data - {len(top_ips)} IPs, {len(suspicious_ips)} suspicious")
    
    suspicious_ip_list = []
    for ip in suspicious_ips:
        if isinstance(ip, dict):
            suspicious_ip_list.append(ip.get('ip', str(ip)))
        else:
            suspicious_ip_list.append(str(ip))
    
    table_data = []
    # Handle both dict and list of tuples formats
    if isinstance(top_ips, dict):
        ip_items = list(top_ips.items())[:20]
    else:
        # Assume it's a list of dicts or tuples
        ip_items = [(item.get('ip', item[0]) if isinstance(item, dict) else item[0], 
                     item.get('count', item[1]) if isinstance(item, dict) else item[1]) 
                    for item in list(top_ips)[:20]]
    
    for ip, count in ip_items:
        table_data.append({
            'ip_address': ip,
            'requests_count': count,
            'suspicious': ip in suspicious_ip_list
        })
    
    logger.debug(f"Prepared {len(table_data)} IPs for display")
    return table_data


def _prepare_endpoints_data(top_endpoints, upload):
    """
    Format endpoints for table with error counts.
    
    Args:
        top_endpoints: Dictionary of URLs and request counts
        upload: LogUpload object for filtering error counts
        
    Returns: List of formatted endpoint data with error counts
    """
    logger.debug(f"Preparing endpoints data from {len(top_endpoints)} endpoints")
    
    table_data = []
    # Handle both dict and list of tuples formats
    if isinstance(top_endpoints, dict):
        endpoint_items = list(top_endpoints.items())[:20]
    else:
        # Assume it's a list of dicts or tuples
        endpoint_items = [(item.get('url', item[0]) if isinstance(item, dict) else item[0], 
                           item.get('count', item[1]) if isinstance(item, dict) else item[1]) 
                          for item in list(top_endpoints)[:20]]
    
    for url, count in endpoint_items:
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
    
    logger.debug(f"Prepared {len(table_data)} endpoints for display")
    return table_data


def _calculate_total_errors(status_codes):
    """
    Calculate total error count from status codes.
    
    Args:
        status_codes: Dictionary of status code categories and counts
        
    Returns: Total count of 4xx and 5xx errors
    """
    error_codes = ['4xx', '5xx']
    total_errors = 0
    for code in error_codes:
        total_errors += status_codes.get(code, 0)
    
    logger.debug(f"Calculated total errors: {total_errors}")
    return total_errors


def _get_current_window_errors(upload):
    """
    Get errors in current time window (last 24 hours).
    
    Args:
        upload: LogUpload object
        
    Returns: Count of errors in the last 24 hours
    """
    current_window = timezone.now() - timedelta(days=1)
    count = ParsedEntry.objects.filter(
        upload=upload,
        status_code__gte=400,
        status_code__lt=600,
        timestamp__gte=current_window
    ).count()
    
    logger.debug(f"Current window errors (last 24h): {count}")
    return count


def _get_previous_window_errors(upload):
    """
    Get errors in previous time window (24-48 hours ago).
    
    Args:
        upload: LogUpload object
        
    Returns: Count of errors from 24-48 hours ago
    """
    end_window = timezone.now() - timedelta(days=1)
    start_window = end_window - timedelta(days=1)
    count = ParsedEntry.objects.filter(
        upload=upload,
        status_code__gte=400,
        status_code__lt=600,
        timestamp__range=(start_window, end_window)
    ).count()
    
    logger.debug(f"Previous window errors (24-48h ago): {count}")
    return count


def _calculate_percent_change(current, previous):
    """
    Calculate percentage change in errors.
    
    Args:
        current: Current period error count
        previous: Previous period error count
        
    Returns: Percentage change (positive for increase, negative for decrease)
    """
    if previous == 0:
        change = 100.0 if current > 0 else 0.0
    else:
        change = ((current - previous) / previous) * 100
    
    logger.debug(f"Percentage change calculated: {change:.1f}% (current: {current}, previous: {previous})")
    return change



# ============================================================================
# FORENSIC SEARCH VIEW
# ============================================================================
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from logs.models import ParsedEntry, LogUpload
import json

import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from logs.models import ParsedEntry, LogUpload
import json

# Get a logger instance
logger = logging.getLogger(__name__)

@login_required
def forensic_search_view(request):
    """
    Advanced search through historical log entries with multiple filters
    """
    logger.info("=" * 80)
    logger.info("FORENSIC SEARCH VIEW CALLED")
    logger.info("=" * 80)
    logger.info(f"User: {request.user.email} (ID: {request.user.id})")
    
    # Add ordering to prevent UnorderedObjectListWarning
    entries = ParsedEntry.objects.filter(
        upload__user=request.user
    ).select_related('upload').order_by('-timestamp')
    
    logger.debug(f"--- INITIAL QUERY ---")
    logger.debug(f"ParsedEntry count for user: {entries.count()}")
    
    # Get filter parameters
    query = request.GET.get('q', '')
    ip_filter = request.GET.get('ip', '')
    status_code = request.GET.get('status', '')
    method = request.GET.get('method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    upload_id = request.GET.get('upload', '')
    sort_by = request.GET.get('sort', '-timestamp')
    
    logger.debug(f"--- FILTER PARAMETERS ---")
    logger.debug(f"query: {query}")
    logger.debug(f"ip_filter: {ip_filter}")
    logger.debug(f"status_code: {status_code}")
    logger.debug(f"method: {method}")
    logger.debug(f"date_from: {date_from}")
    logger.debug(f"date_to: {date_to}")
    logger.debug(f"upload_id: {upload_id}")
    logger.debug(f"sort_by: {sort_by}")
    
    # Apply filters
    if query:
        entries = entries.filter(
            Q(url__icontains=query) | 
            Q(user_agent__icontains=query) |
            Q(ip_address__icontains=query)
        )
        logger.debug(f"After query filter: {entries.count()} entries")
    
    if ip_filter:
        entries = entries.filter(ip_address__icontains=ip_filter)
        logger.debug(f"After IP filter: {entries.count()} entries")
    
    if status_code and status_code.isdigit():
        entries = entries.filter(status_code=int(status_code))
        logger.debug(f"After status code filter: {entries.count()} entries")
    
    if method:
        entries = entries.filter(method__iexact=method)
        logger.debug(f"After method filter: {entries.count()} entries")
    
    if date_from:
        entries = entries.filter(timestamp__date__gte=date_from)
        logger.debug(f"After date_from filter: {entries.count()} entries")
    
    if date_to:
        entries = entries.filter(timestamp__date__lte=date_to)
        logger.debug(f"After date_to filter: {entries.count()} entries")
    
    if upload_id and upload_id.isdigit():
        entries = entries.filter(upload_id=int(upload_id))
        logger.debug(f"After upload filter: {entries.count()} entries")
    
    # Apply sorting
    if sort_by in ['timestamp', '-timestamp', 'ip_address', '-ip_address', 'status_code', '-status_code']:
        entries = entries.order_by(sort_by)
        logger.debug(f"Sorting by: {sort_by}")
    else:
        entries = entries.order_by('-timestamp')
        logger.debug("Sorting by: -timestamp (default)")
    
    logger.debug(f"--- FILTER DROPDOWN DATA ---")
    
    # Status codes
    unique_status_codes = list(ParsedEntry.objects.filter(
        upload__user=request.user,
        status_code__isnull=False
    ).values_list('status_code', flat=True).distinct().order_by('status_code'))
    
    logger.debug(f"Unique status codes from DB: {unique_status_codes}")
    
    if not unique_status_codes:
        unique_status_codes = [200, 201, 204, 301, 302, 400, 401, 403, 404, 500, 502, 503]
        logger.debug(f"Using fallback status codes: {unique_status_codes}")
    
    # HTTP Methods
    unique_methods = list(ParsedEntry.objects.filter(
        upload__user=request.user,
        method__isnull=False
    ).values_list('method', flat=True).distinct().order_by('method'))
    
    logger.debug(f"Unique methods from DB: {unique_methods}")
    
    if not unique_methods:
        unique_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        logger.debug(f"Using fallback methods: {unique_methods}")
    
    # Get unique IPs for suggestions
    unique_ips = ParsedEntry.objects.filter(
        upload__user=request.user,
        ip_address__isnull=False
    ).values_list('ip_address', flat=True).distinct()[:20]
    
    logger.debug(f"Unique IPs (first 20): {list(unique_ips)}")
    
    # ========== GET USER'S UPLOADS ==========
    logger.debug(f"--- USER UPLOADS ---")
    
    # Direct query for user uploads
    user_uploads = LogUpload.objects.filter(user=request.user).order_by('-uploaded_at')
    
    logger.debug(f"user_uploads.query: {user_uploads.query}")
    logger.debug(f"user_uploads.count(): {user_uploads.count()}")
    
    if user_uploads.exists():
        for upload in user_uploads:
            logger.debug(f"  - Upload ID: {upload.id}, Type: {upload.log_type}, Date: {upload.uploaded_at}, Status: {upload.status}")
            entries_count = upload.entries.count()
            logger.debug(f"    Entries: {entries_count}")
    else:
        logger.debug("No uploads found for this user")
    
    # Check all uploads in database
    all_uploads = LogUpload.objects.all()
    logger.debug(f"All uploads in database: {all_uploads.count()}")
    for upload in all_uploads:
        logger.debug(f"  - Upload ID: {upload.id}, User: {upload.user.email}, Type: {upload.log_type}")
    
    # Check if user has entries without uploads (shouldn't happen)
    entries_without_uploads = ParsedEntry.objects.filter(upload__user=request.user).exclude(upload__in=user_uploads)
    if entries_without_uploads.exists():
        logger.warning(f"Found {entries_without_uploads.count()} entries with uploads not in user_uploads queryset")
    
    # Debug info to help identify the issue
    debug_info = {
        'uploads_count': user_uploads.count(),
        'user_id': request.user.id,
        'user_email': request.user.email,
        'total_uploads_in_db': LogUpload.objects.count(),
        'entries_count': ParsedEntry.objects.filter(upload__user=request.user).count(),
        'all_uploads_list': [(u.id, u.user.email, u.log_type) for u in all_uploads],
    }
    
    logger.debug(f"--- DEBUG INFO ---")
    logger.debug(f"uploads_count: {debug_info['uploads_count']}")
    logger.debug(f"user_id: {debug_info['user_id']}")
    logger.debug(f"user_email: {debug_info['user_email']}")
    logger.debug(f"total_uploads_in_db: {debug_info['total_uploads_in_db']}")
    logger.debug(f"entries_count: {debug_info['entries_count']}")
    logger.debug(f"all_uploads_list: {debug_info['all_uploads_list']}")
    
    # Pagination
    paginator = Paginator(entries, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    logger.debug(f"--- PAGINATION ---")
    logger.debug(f"Total entries after filters: {entries.count()}")
    logger.debug(f"Page number: {page_number}")
    logger.debug(f"Items on current page: {len(page_obj)}")
    
    # Get counts for summary
    total_matching = entries.count()
    unique_ips_count = entries.values('ip_address').distinct().count()
    
    logger.info(f"--- SUMMARY ---")
    logger.info(f"total_matching: {total_matching}")
    logger.info(f"unique_ips_count: {unique_ips_count}")
    logger.info("=" * 80 + "\n")
    
    # Prepare context
    context = {
        'page_obj': page_obj,
        'total_matching': total_matching,
        'unique_ips_count': unique_ips_count,
        'unique_ips': unique_ips,
        'unique_status_codes': unique_status_codes,
        'unique_methods': unique_methods,
        'user_uploads': user_uploads,
        'debug_info': debug_info,  # Add debug info to context
        
        # Preserve filter values in template
        'query': query,
        'ip_filter': ip_filter,
        'status_filter': status_code,
        'method_filter': method,
        'date_from': date_from,
        'date_to': date_to,
        'upload_filter': upload_id,
        'sort_by': sort_by,
        
        # Add request to context for URL parameters
        'request': request,
    }
    
    return render(request, 'analytics/forensic_search.html', context)

def get_status_distribution(queryset):
    """Helper to get status code distribution for charts"""
    distribution = {}
    for entry in queryset:
        if entry.status_code:
            code_class = f"{str(entry.status_code)[0]}xx"
            distribution[code_class] = distribution.get(code_class, 0) + 1
    return distribution


def get_hourly_activity(queryset):
    """Helper to get hourly activity for charts"""
    hourly = {}
    for entry in queryset:
        hour = entry.timestamp.hour
        hourly[hour] = hourly.get(hour, 0) + 1
    return hourly


@login_required
def export_search_results(request):
    """Export search results as CSV/JSON"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entry_ids = data.get('entry_ids', [])
            export_format = data.get('format', 'csv')
            
            entries = ParsedEntry.objects.filter(
                id__in=entry_ids,
                upload__user=request.user
            ).select_related('upload').order_by('-timestamp')
            
            if export_format == 'csv':
                # Generate CSV response
                import csv
                from django.http import HttpResponse
                
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="search_results.csv"'
                
                writer = csv.writer(response)
                writer.writerow(['Timestamp', 'IP Address', 'Method', 'URL', 'Status Code', 'User Agent', 'Log Source'])
                
                for entry in entries:
                    writer.writerow([
                        entry.timestamp,
                        entry.ip_address,
                        entry.method or '-',
                        entry.url or '-',
                        entry.status_code or '-',
                        entry.user_agent or '-',
                        entry.upload.get_log_type_display()
                    ])
                
                return response
            
            elif export_format == 'json':
                # Generate JSON response
                from django.http import JsonResponse
                
                data = []
                for entry in entries:
                    data.append({
                        'timestamp': entry.timestamp.isoformat(),
                        'ip_address': entry.ip_address,
                        'method': entry.method,
                        'url': entry.url,
                        'status_code': entry.status_code,
                        'user_agent': entry.user_agent,
                        'log_source': entry.upload.get_log_type_display(),
                    })
                
                return JsonResponse({'data': data}, json_dumps_params={'indent': 2})
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)