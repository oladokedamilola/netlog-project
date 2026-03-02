"""
Logs App Views
=============
This module handles all log-related views including log upload, processing,
history viewing, and detailed log analysis.

Each view includes proper logging for monitoring and debugging purposes.
"""

from django.db.models import Count
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
import threading
import logging

# Local application imports
from .forms import LogUploadForm
from .models import LogUpload, ParsedEntry
from .utils.parser_selector import get_parser
from analytics.utils.analyzer import LogAnalyzer
from analytics.models import Analysis

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# LOG UPLOAD VIEWS
# ============================================================================

@login_required
def upload_log(request):
    """
    Handle log file upload and processing.
    
    This view:
    1. Displays upload form (GET request)
    2. Processes uploaded log file (POST request)
    3. Supports both AJAX and traditional form submissions
    4. Parses the log file based on selected log type
    5. Saves parsed entries to database
    6. Performs analysis on the parsed data
    
    Template: logs/upload.html
    
    AJAX Response:
        - Success: {status: 'success', redirect_url: url, message: string}
        - Error: {status: 'error', message: string} (status 500)
    """
    logger.info("=" * 50)
    logger.info("UPLOAD LOG VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    logger.info(f"Request method: {request.method}")
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        logger.info("AJAX request detected")
    
    if request.method == "POST":
        logger.info("Processing log upload form submission")
        form = LogUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            logger.info("Form is valid, saving upload")
            
            # Save the upload
            log = form.save(commit=False)
            log.user = request.user
            log.status = 'processing'  # Set initial status
            log.save()
            
            logger.info(f"Log upload saved with ID: {log.id}, Type: {log.log_type}, File: {log.file.name}")
            
            # Handle AJAX request
            if is_ajax:
                logger.info("Processing AJAX upload request")
                return _process_upload_ajax(request, log)
            else:
                # Regular form submission (non-AJAX)
                logger.info("Processing regular form submission")
                return _process_upload_sync(request, log)
        else:
            # Form is invalid
            logger.warning("Upload form is invalid")
            logger.warning(f"Form errors: {form.errors}")
            
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please correct the errors in the form.'
                }, status=400)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
    else:
        # GET request - display empty form
        logger.info("Displaying empty upload form")
        form = LogUploadForm()

    context = {"form": form}
    return render(request, "logs/upload.html", context)


def _process_upload_ajax(request, log):
    """
    Process log upload for AJAX requests synchronously.
    
    Args:
        request: HTTP request object
        log: LogUpload instance
        
    Returns:
        JsonResponse with success/error status
    """
    logger.info("=" * 40)
    logger.info("PROCESSING AJAX UPLOAD")
    logger.info("=" * 40)
    
    try:
        # Parse the log file
        logger.info(f"Starting log parsing for upload {log.id}")
        file_path = log.file.path
        parser = get_parser(log.log_type, file_path)
        logger.info(f"Using parser: {parser.__class__.__name__}")
        
        # Save parsed entries
        entries_count = 0
        for row in parser.parse_file():
            ParsedEntry.objects.create(
                upload=log,
                ip_address=row["ip"],
                timestamp=row["timestamp"],
                method=row.get("method", ""),
                status_code=row.get("status"),
                url=row.get("url", ""),
                user_agent=row.get("user_agent", ""),
            )
            entries_count += 1
        
        logger.info(f"Successfully parsed {entries_count} log entries")
        
        # Update status
        log.status = 'completed'
        log.processed_at = timezone.now()
        log.save()
        logger.info(f"Upload status updated to 'completed'")
        
        # Run analysis
        logger.info("Starting log analysis")
        analyzer = LogAnalyzer(log)
        analysis_data = analyzer.analyze()
        logger.info("Analysis completed successfully")
        
        # Save analysis results
        analysis, created = Analysis.objects.update_or_create(
            upload=log,
            defaults={
                'user': request.user,
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
        
        action = "Created" if created else "Updated"
        logger.info(f"{action} analysis record for upload {log.id}")
        
        # Return JSON response with redirect URL
        response_data = {
            'status': 'success',
            'redirect_url': reverse('analytics_view', kwargs={'upload_id': log.id}),
            'message': f'Analysis complete! Processed {entries_count} log entries.'
        }
        logger.info("AJAX processing successful, returning success response")
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error processing log in AJAX: {str(e)}", exc_info=True)
        log.status = 'failed'
        log.error_message = str(e)[:200]
        log.save()
        logger.info(f"Upload status updated to 'failed'")
        
        return JsonResponse({
            'status': 'error',
            'message': 'Error processing log file. Please check the format and try again.'
        }, status=500)


def _process_upload_sync(request, log):
    """
    Process log upload for regular form submissions synchronously.
    
    Args:
        request: HTTP request object
        log: LogUpload instance
        
    Returns:
        HttpResponse redirect
    """
    logger.info("=" * 40)
    logger.info("PROCESSING SYNC UPLOAD")
    logger.info("=" * 40)
    
    messages.success(request, "File uploaded successfully! Processing analysis...")
    
    try:
        # Parse the log file
        logger.info(f"Starting log parsing for upload {log.id}")
        from .utils.parser_selector import get_parser
        file_path = log.file.path
        parser = get_parser(log.log_type, file_path)
        logger.info(f"Using parser: {parser.__class__.__name__}")
        
        entries_count = 0
        for row in parser.parse_file():
            ParsedEntry.objects.create(
                upload=log,
                ip_address=row["ip"],
                timestamp=row["timestamp"],
                method=row.get("method", ""),
                status_code=row.get("status"),
                url=row.get("url", ""),
                user_agent=row.get("user_agent", ""),
            )
            entries_count += 1
        
        logger.info(f"Successfully parsed {entries_count} log entries")
        
        # Update status
        log.status = 'completed'
        log.processed_at = timezone.now()
        log.save()
        logger.info(f"Upload status updated to 'completed'")
        
        # Run analysis
        logger.info("Starting log analysis")
        analyzer = LogAnalyzer(log)
        analysis_data = analyzer.analyze()
        logger.info("Analysis completed successfully")
        
        # Save analysis results
        analysis, created = Analysis.objects.update_or_create(
            upload=log,
            defaults={
                'user': request.user,
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
        
        action = "Created" if created else "Updated"
        logger.info(f"{action} analysis record for upload {log.id}")
        
        messages.success(request, f"Analysis complete! Processed {entries_count} log entries.")
        return redirect('analytics_view', upload_id=log.id)
        
    except Exception as e:
        logger.error(f"Error processing log synchronously: {str(e)}", exc_info=True)
        log.status = 'failed'
        log.error_message = str(e)[:200]
        log.save()
        logger.info(f"Upload status updated to 'failed'")
        
        messages.error(request, "Error processing log file. Please check the format and try again.")
        return redirect('logs:upload_history')


# ============================================================================
# LOG HISTORY AND DETAIL VIEWS
# ============================================================================

@login_required
def upload_history(request):
    """
    Display user's upload history.
    
    This view:
    1. Lists all log uploads by the current user
    2. Adds entry counts for each upload
    3. Orders by most recent first
    
    Template: logs/history.html
    """
    logger.info("=" * 50)
    logger.info("UPLOAD HISTORY VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    uploads = LogUpload.objects.filter(user=request.user).order_by("-uploaded_at")
    logger.info(f"Found {uploads.count()} uploads for user")
    
    # Add entry counts for each upload
    for upload in uploads:
        upload.entries_count = upload.entries.count()
    
    logger.info("Added entry counts to uploads")
    
    return render(request, "logs/history.html", {"uploads": uploads})


@login_required
def upload_detail(request, upload_id):
    """
    Display detailed information about a specific log upload.
    
    This view:
    1. Retrieves the specified upload
    2. Shows file metadata and parsing statistics
    3. Displays a preview of the first 10 log entries
    
    Args:
        upload_id: ID of the LogUpload to view
        
    Template: logs/upload_detail.html
    """
    logger.info("=" * 50)
    logger.info("UPLOAD DETAIL VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}, Upload ID: {upload_id}")
    
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    logger.info(f"Upload found: {upload.file.name}")
    
    # Get entries for this upload
    entries = ParsedEntry.objects.filter(upload=upload).order_by('timestamp')
    total_entries = entries.count()
    logger.info(f"Total entries: {total_entries}")
    
    # Get first and last entry for time range
    first_entry = entries.first()
    last_entry = entries.last()
    
    # FIXED: Use Python's strftime() instead of template filters
    if first_entry and last_entry:
        time_range = f"{first_entry.timestamp.strftime('%Y-%m-%d %H:%M')} - {last_entry.timestamp.strftime('%H:%M')}"
    else:
        time_range = "N/A"
    
    # Get unique IPs count
    unique_ips = entries.values('ip_address').distinct().count()
    
    # Get status code breakdown
    status_breakdown = {}
    for entry in entries:
        if entry.status_code:
            code_class = f"{str(entry.status_code)[0]}xx"
            status_breakdown[code_class] = status_breakdown.get(code_class, 0) + 1
    
    # Calculate counts for status categories
    success_count = sum(v for k, v in status_breakdown.items() if k.startswith('2'))
    redirect_count = sum(v for k, v in status_breakdown.items() if k.startswith('3'))
    error_count = sum(v for k, v in status_breakdown.items() if k.startswith(('4', '5')))
    
    # Calculate percentages
    if total_entries > 0:
        success_rate = (success_count / total_entries) * 100
        redirect_rate = (redirect_count / total_entries) * 100
        error_rate = (error_count / total_entries) * 100
    else:
        success_rate = redirect_rate = error_rate = 0
    
    # Get preview entries (first 10)
    preview_entries = entries[:10]
    
    # Get method breakdown
    methods_breakdown = {}
    for entry in entries:
        if entry.method:
            methods_breakdown[entry.method] = methods_breakdown.get(entry.method, 0) + 1
    
    context = {
        'upload': upload,
        'total_entries': total_entries,
        'unique_ips': unique_ips,
        'time_range': time_range,  # Now this is a properly formatted string
        'status_breakdown': status_breakdown,
        'methods_breakdown': methods_breakdown,
        'success_count': success_count,
        'redirect_count': redirect_count,
        'error_count': error_count,
        'success_rate': round(success_rate, 1),
        'redirect_rate': round(redirect_rate, 1),
        'error_rate': round(error_rate, 1),
        'preview_entries': preview_entries,
        'active_tab': 'uploads',
    }
    
    logger.info(f"Context prepared - Total entries: {total_entries}, Unique IPs: {unique_ips}")
    logger.info("Rendering upload detail template")
    
    return render(request, 'logs/upload_detail.html', context)


# ============================================================================
# LEGACY PROCESSING VIEW (Maintained for backward compatibility)
# ============================================================================

@login_required
def process_log(request, upload_id):
    """
    Legacy view to process a log file (maintained for backward compatibility).
    
    This view:
    1. Retrieves the log upload
    2. Parses the file
    3. Creates ParsedEntry objects
    4. Redirects to analytics dashboard
    
    Args:
        upload_id: ID of the LogUpload to process
        
    Note: This is an older version. New code should use upload_log view.
    """
    logger.info("=" * 50)
    logger.info("PROCESS LOG VIEW CALLED (LEGACY)")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}, Upload ID: {upload_id}")
    
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    logger.info(f"Processing legacy log: {upload.id}")
    
    file_path = upload.file.path
    logger.info(f"File path: {file_path}")

    parser = get_parser(upload.log_type, file_path)
    logger.info(f"Using parser: {parser.__class__.__name__}")

    entries_count = 0
    for row in parser.parse_file():
        ParsedEntry.objects.create(
            upload=upload,
            ip_address=row["ip"],
            timestamp=row["timestamp"],
            method=row["method"],
            status_code=row["status"],
            url=row["url"],
            user_agent=row["user_agent"],
        )
        entries_count += 1
    
    logger.info(f"Created {entries_count} parsed entries")

    logger.info(f"Redirecting to analytics_dashboard for upload {upload.id}")
    return redirect("analytics_dashboard", upload_id=upload.id)



# ============================================================================
# ASYNC PROCESSING IMPLEMENTATION (Commented out for future use)
# ============================================================================

"""
Note: The following code is for asynchronous processing and is currently commented out.
It can be enabled when you're ready to implement background processing.

def process_log_async(upload_id):
    '''Process log in background thread'''
    logger.info(f"Starting background processing for upload {upload_id}")
    
    from django.db import connection
    connection.close()  # Close the connection for the new thread
    
    try:
        log = LogUpload.objects.get(id=upload_id)
        logger.info(f"Retrieved log {upload_id} for background processing")
        
        from .utils.parser_selector import get_parser
        
        file_path = log.file.path
        parser = get_parser(log.log_type, file_path)
        logger.info(f"Using parser: {parser.__class__.__name__}")
        
        # Save parsed entries
        entries_count = 0
        for row in parser.parse_file():
            ParsedEntry.objects.create(
                upload=log,
                ip_address=row["ip"],
                timestamp=row["timestamp"],
                method=row.get("method", ""),
                status_code=row.get("status"),
                url=row.get("url", ""),
                user_agent=row.get("user_agent", ""),
            )
            entries_count += 1
        
        logger.info(f"Background processing created {entries_count} entries")
        
        # Run analysis
        analyzer = LogAnalyzer(log)
        analysis_data = analyzer.analyze()
        logger.info("Background analysis completed")
        
        # Save analysis results
        Analysis.objects.update_or_create(
            upload=log,
            defaults={
                'user': log.user,
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
        logger.info(f"Analysis saved for upload {upload_id}")
        
        # Optionally update upload with processing status
        log.status = 'completed'
        log.save()
        logger.info(f"Upload {upload_id} marked as completed")
        
    except Exception as e:
        logger.error(f"Background processing error for upload {upload_id}: {str(e)}", exc_info=True)
        # Update upload with error status
        try:
            log = LogUpload.objects.get(id=upload_id)
            log.status = 'failed'
            log.error_message = str(e)[:200]
            log.save()
            logger.info(f"Upload {upload_id} marked as failed")
        except:
            logger.error(f"Could not update upload {upload_id} with error status")


@login_required
def upload_log_async(request):
    '''Upload log view using async processing'''
    logger.info("=" * 50)
    logger.info("UPLOAD LOG ASYNC VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    if request.method == "POST":
        logger.info("Processing async upload form submission")
        form = LogUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            logger.info("Form is valid, saving upload")
            
            # Save the upload
            log = form.save(commit=False)
            log.user = request.user
            log.status = 'processing'
            log.save()
            
            logger.info(f"Log upload saved with ID: {log.id}")
            
            messages.success(request, "File uploaded successfully! Processing in background...")
            
            # Start background thread
            import threading
            thread = threading.Thread(target=process_log_async, args=(log.id,))
            thread.daemon = True
            thread.start()
            logger.info(f"Background thread started for upload {log.id}")
            
            # Redirect to history with processing indicator
            return redirect('logs:upload_history')
        else:
            logger.warning("Upload form is invalid")
            logger.warning(f"Form errors: {form.errors}")
    else:
        logger.info("Displaying empty upload form")
        form = LogUploadForm()

    context = {"form": form}
    return render(request, "logs/upload.html", context)
"""