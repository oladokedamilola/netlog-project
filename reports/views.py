# reports/views.py
"""
Reports App Views
================
This module handles all report-related views including report generation,
downloading, listing, and previewing generated reports.

Each view includes proper logging for monitoring and debugging purposes.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, FileResponse
from django.utils import timezone
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
import json
import csv
import io
import time
from datetime import datetime
import logging

# Local application imports
from logs.models import LogUpload, ParsedEntry
from analytics.models import Analysis
from .models import GeneratedReport, ReportTemplate
from .forms import ReportGenerationForm, QuickReportForm
from .utils.report_generators import (
    generate_pdf_report,
    generate_csv_report,
    generate_html_report,
    generate_json_report,
)

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# REPORT GENERATION VIEWS
# ============================================================================

@login_required
def generate_report(request):
    """
    Main report generation view with form.
    
    This view:
    1. Displays report generation form (GET request)
    2. Processes form submission (POST request)
    3. Collects report data based on selected options
    4. Generates report in requested format (PDF, CSV, HTML, JSON)
    5. Saves report to database and storage
    6. Redirects to report detail page
    
    Template: reports/generate.html
    
    Form Data:
        - upload: Selected log upload
        - report_type: Type of report (summary, detailed, etc.)
        - format: Output format (pdf, csv, html, json)
        - title: Report title
        - description: Report description
        - date_range: Date filter option
        - start_date/end_date: Custom date range
        - include_* options: Content inclusion toggles
    """
    logger.info("=" * 50)
    logger.info("GENERATE REPORT VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    logger.info(f"Request method: {request.method}")
    
    if request.method == 'POST':
        logger.info("Processing report generation form submission")
        form = ReportGenerationForm(request.user, request.POST)
        
        if form.is_valid():
            logger.info("Form is valid, generating report")
            
            # Start timing
            start_time = time.time()
            logger.info(f"Report generation started at: {time.ctime()}")
            
            # Get form data
            upload = form.cleaned_data['upload']
            report_type = form.cleaned_data['report_type']
            report_format = form.cleaned_data['format']
            title = form.cleaned_data['title']
            description = form.cleaned_data['description']
            
            logger.info(f"Report parameters - Upload: {upload.id}, Type: {report_type}, Format: {report_format}")
            logger.info(f"Title: {title}")
            
            # Get or create analysis
            analysis, created = Analysis.objects.get_or_create(
                upload=upload,
                defaults={'user': request.user}
            )
            
            if created:
                logger.info(f"Created new analysis for upload {upload.id}")
            else:
                logger.info(f"Retrieved existing analysis for upload {upload.id}")
            
            # Apply date filters if specified
            entries = ParsedEntry.objects.filter(upload=upload)
            date_range = form.cleaned_data.get('date_range')
            
            logger.info(f"Date range filter: {date_range}")
            
            if date_range == 'last7':
                cutoff = timezone.now() - timezone.timedelta(days=7)
                entries = entries.filter(timestamp__gte=cutoff)
                logger.info(f"Filtered to last 7 days (since {cutoff})")
            elif date_range == 'last30':
                cutoff = timezone.now() - timezone.timedelta(days=30)
                entries = entries.filter(timestamp__gte=cutoff)
                logger.info(f"Filtered to last 30 days (since {cutoff})")
            elif date_range == 'custom':
                start_date = form.cleaned_data.get('start_date')
                end_date = form.cleaned_data.get('end_date')
                if start_date and end_date:
                    entries = entries.filter(
                        timestamp__date__range=(start_date, end_date)
                    )
                    logger.info(f"Filtered to custom range: {start_date} to {end_date}")
            
            entry_count = entries.count()
            logger.info(f"Total entries after filtering: {entry_count}")
            
            # ========== FIXED: Serialize data for JSON field and pass to generators ==========
            # Create a serializable copy for the JSON field
            report_data_serializable = {
                'title': title,
                'description': description,
                'report_type': report_type,
                'upload_id': upload.id,
                'upload_filename': upload.file.name,
                'upload_log_type': upload.log_type,
                'upload_date': upload.uploaded_at.isoformat() if upload.uploaded_at else None,
                'analysis_id': analysis.id if analysis else None,
                'filters': {
                    'date_range': date_range,
                    'start_date': form.cleaned_data.get('start_date').isoformat() if form.cleaned_data.get('start_date') else None,
                    'end_date': form.cleaned_data.get('end_date').isoformat() if form.cleaned_data.get('end_date') else None,
                },
                'options': {
                    'include_summary': form.cleaned_data.get('include_summary', True),
                    'include_charts': form.cleaned_data.get('include_charts', True),
                    'include_top_data': form.cleaned_data.get('include_top_data', True),
                    'include_recommendations': form.cleaned_data.get('include_recommendations', True),
                },
                'generated_at': timezone.now().isoformat(),
                'entry_count': entry_count,
            }
            
            # Add analysis data if available (as a dictionary)
            if analysis:
                report_data_serializable['analysis'] = {
                    'total_requests': analysis.total_requests,
                    'unique_ips': analysis.unique_ips,
                    'error_rate': analysis.error_rate,
                    'avg_requests_per_day': analysis.avg_requests_per_day,
                    'time_period_days': analysis.time_period_days,
                    'top_ips': analysis.top_ips,
                    'status_codes': analysis.status_codes,
                    'top_endpoints': analysis.top_endpoints,
                    'suspicious_ips': analysis.suspicious_ips,
                    'top_user_agents': analysis.top_user_agents,
                    'hourly_distribution': analysis.hourly_distribution,
                    'daily_distribution': analysis.daily_distribution,
                }
            
            # Create a data dictionary for the report generators (with objects)
            report_data_for_generators = {
                'title': title,
                'description': description,
                'report_type': report_type,
                'upload': upload,  # Keep the object for generators that need it
                'analysis': analysis,  # Keep the object for generators that need it
                'entries': entries,  # Keep the queryset for generators that need it
                'filters': {
                    'date_range': date_range,
                    'start_date': form.cleaned_data.get('start_date'),
                    'end_date': form.cleaned_data.get('end_date'),
                },
                'options': {
                    'include_summary': form.cleaned_data.get('include_summary', True),
                    'include_charts': form.cleaned_data.get('include_charts', True),
                    'include_top_data': form.cleaned_data.get('include_top_data', True),
                    'include_recommendations': form.cleaned_data.get('include_recommendations', True),
                },
                'generated_at': timezone.now(),
                'entry_count': entry_count,
            }
            
            logger.info(f"Report data prepared - Using object-based data for generators")
            
            # Generate the report file using the object-based data
            logger.info(f"Generating {report_format.upper()} report...")
            
            if report_format == 'pdf':
                file_content = generate_pdf_report(report_data_for_generators)
                file_extension = '.pdf'
                content_type = 'application/pdf'
            elif report_format == 'csv':
                file_content = generate_csv_report(report_data_for_generators)
                file_extension = '.csv'
                content_type = 'text/csv'
            elif report_format == 'html':
                file_content = generate_html_report(report_data_for_generators)
                file_extension = '.html'
                content_type = 'text/html'
            else:  # json
                file_content = generate_json_report(report_data_for_generators)
                file_extension = '.json'
                content_type = 'application/json'
            
            content_size = len(file_content) if file_content else 0
            logger.info(f"Report generated successfully - Size: {content_size} bytes")
            
            # Create report record using the serializable data for the JSON field
            generation_time = time.time() - start_time
            logger.info(f"Generation time: {generation_time:.2f} seconds")
            
            report = GeneratedReport.objects.create(
                user=request.user,
                upload=upload,
                report_type=report_type,
                format=report_format,
                title=title,
                description=description,
                report_data=report_data_serializable,  # Store serializable data in JSON field
                generation_time=generation_time,
            )
            logger.info(f"Report record created with ID: {report.id}")
            
            # Save file
            filename = f"report_{report.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}{file_extension}"
            report.file.save(filename, ContentFile(file_content))
            report.file_size = content_size
            report.save()
            logger.info(f"Report file saved as: {filename}")
            
            logger.info(f"Redirecting to report detail page for report {report.id}")
            return redirect('reports:report_detail', report_id=report.id)
        else:
            logger.warning("Report generation form is invalid")
            logger.warning(f"Form errors: {form.errors}")
    else:
        logger.info("Displaying empty report generation form")
        form = ReportGenerationForm(request.user)
    
    # Get user's recent uploads for quick access
    recent_uploads = LogUpload.objects.filter(user=request.user).order_by('-uploaded_at')[:5]
    logger.info(f"Retrieved {recent_uploads.count()} recent uploads for context")
    
    context = {
        'form': form,
        'recent_uploads': recent_uploads,
        'active_tab': 'generate',
    }
    
    logger.info("Rendering report generation template")
    return render(request, 'reports/generate.html', context)


@login_required
def quick_report(request):
    """
    Generate a quick report from analytics page.
    
    This view:
    1. Processes quick report form from analytics page
    2. Generates a summary report with default title
    3. Creates report in PDF or CSV format
    4. Redirects to download page
    
    Template: No template - redirects to download
    
    Form Data:
        - upload: Selected log upload
        - format: Output format (pdf or csv)
    """
    logger.info("=" * 50)
    logger.info("QUICK REPORT VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    logger.info(f"Request method: {request.method}")
    
    if request.method == 'POST':
        logger.info("Processing quick report form submission")
        form = QuickReportForm(request.POST)
        
        if form.is_valid():
            upload = form.cleaned_data['upload']
            report_format = form.cleaned_data['format']
            
            logger.info(f"Quick report parameters - Upload: {upload.id}, Format: {report_format}")
            
            # Generate a default title
            title = f"{upload.get_log_type_display()} Log Analysis - {timezone.now().strftime('%Y-%m-%d')}"
            logger.info(f"Generated title: {title}")
            
            # Get analysis
            analysis, created = Analysis.objects.get_or_create(
                upload=upload,
                defaults={'user': request.user}
            )
            
            if created:
                logger.info(f"Created new analysis for upload {upload.id}")
            else:
                logger.info(f"Retrieved existing analysis for upload {upload.id}")
            
            # Create report data (limited entries for quick report)
            entries = ParsedEntry.objects.filter(upload=upload)[:1000]
            entry_count = entries.count()
            logger.info(f"Quick report includes {entry_count} entries (limited to 1000)")
            
            # ========== FIXED: Create both serializable and object-based data ==========
            # Serializable data for JSON field
            report_data_serializable = {
                'title': title,
                'description': f'Quick report generated from {upload.file.name}',
                'report_type': 'summary',
                'upload_id': upload.id,
                'upload_filename': upload.file.name,
                'upload_log_type': upload.log_type,
                'upload_date': upload.uploaded_at.isoformat() if upload.uploaded_at else None,
                'analysis_id': analysis.id if analysis else None,
                'generated_at': timezone.now().isoformat(),
                'entry_count': entry_count,
            }
            
            # Add analysis data as dictionary
            if analysis:
                report_data_serializable['analysis'] = {
                    'total_requests': analysis.total_requests,
                    'unique_ips': analysis.unique_ips,
                    'error_rate': analysis.error_rate,
                    'avg_requests_per_day': analysis.avg_requests_per_day,
                    'time_period_days': analysis.time_period_days,
                    'top_ips': analysis.top_ips,
                    'status_codes': analysis.status_codes,
                    'top_endpoints': analysis.top_endpoints,
                    'suspicious_ips': analysis.suspicious_ips,
                }
            
            # Object-based data for generators
            report_data_for_generators = {
                'title': title,
                'description': f'Quick report generated from {upload.file.name}',
                'report_type': 'summary',
                'upload': upload,
                'analysis': analysis,
                'entries': entries,
                'generated_at': timezone.now(),
                'entry_count': entry_count,
            }
            
            # Generate file using object-based data
            logger.info(f"Generating {report_format.upper()} quick report...")
            
            if report_format == 'pdf':
                file_content = generate_pdf_report(report_data_for_generators)
                file_extension = '.pdf'
            else:  # csv
                file_content = generate_csv_report(report_data_for_generators)
                file_extension = '.csv'
            
            content_size = len(file_content) if file_content else 0
            logger.info(f"Quick report generated - Size: {content_size} bytes")
            
            # Create report record using serializable data
            report = GeneratedReport.objects.create(
                user=request.user,
                upload=upload,
                report_type='summary',
                format=report_format,
                title=title,
                report_data=report_data_serializable,
            )
            logger.info(f"Quick report record created with ID: {report.id}")
            
            # Save file
            filename = f"quick_report_{report.id}{file_extension}"
            report.file.save(filename, ContentFile(file_content))
            report.file_size = content_size
            report.save()
            logger.info(f"Quick report file saved as: {filename}")
            
            logger.info(f"Redirecting to download page for report {report.id}")
            return redirect('reports:download_report', report_id=report.id)
        else:
            logger.warning("Quick report form is invalid")
            logger.warning(f"Form errors: {form.errors}")
    
    logger.warning("Invalid request method or form, redirecting to generate report page")
    return redirect('reports:generate_report')

# ============================================================================
# REPORT MANAGEMENT VIEWS
# ============================================================================

@login_required
def report_detail(request, report_id):
    """
    View report details and download options.
    
    This view:
    1. Retrieves the specified report
    2. Displays report metadata and download options
    
    Args:
        report_id: ID of the GeneratedReport to view
        
    Template: reports/detail.html
    """
    logger.info("=" * 50)
    logger.info("REPORT DETAIL VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}, Report ID: {report_id}")
    
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    logger.info(f"Report found: {report.title}")
    logger.info(f"Report details - Format: {report.format}, Type: {report.report_type}, Size: {report.file_size} bytes")
    
    # Extract summary data from report_data for template
    summary_data = {}
    analysis_data = {}
    
    if report.report_data and isinstance(report.report_data, dict):
        # Check if analysis_summary exists (from your template)
        if 'analysis_summary' in report.report_data:
            analysis_data = report.report_data.get('analysis_summary', {})
        # Check if analysis exists (from our view)
        elif 'analysis' in report.report_data:
            analysis_data = report.report_data.get('analysis', {})
        
        # Extract metrics from analysis_data
        summary_data = {
            'total_requests': analysis_data.get('total_requests', 0),
            'unique_ips': analysis_data.get('unique_ips', 0),
            'error_rate': analysis_data.get('error_rate', 0),
            'avg_requests_per_day': analysis_data.get('avg_requests_per_day', 0),
            'time_period_days': analysis_data.get('time_period_days', 0),
            'status_codes': analysis_data.get('status_codes', {}),
            'top_ips': analysis_data.get('top_ips', {}),
            'top_endpoints': analysis_data.get('top_endpoints', {}),
            'suspicious_ips': analysis_data.get('suspicious_ips', []),
        }
        
        logger.info(f"Extracted summary data: {summary_data}")
    
    context = {
        'report': report,
        'summary_data': summary_data,  # Pass extracted summary data
        'active_tab': 'reports',
    }
    
    logger.info("Rendering report detail template")
    return render(request, 'reports/detail.html', context)


@login_required
def download_report(request, report_id):
    """
    Download generated report file.
    
    This view:
    1. Retrieves the specified report
    2. Marks it as downloaded (increments download count)
    3. Returns the file as a downloadable attachment
    
    Args:
        report_id: ID of the GeneratedReport to download
        
    Returns:
        FileResponse with the report file for download
    """
    logger.info("=" * 50)
    logger.info("DOWNLOAD REPORT VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}, Report ID: {report_id}")
    
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    logger.info(f"Report found: {report.title}")
    
    if not report.file:
        logger.error(f"Report file not found for report {report_id}")
        return HttpResponse("Report file not found", status=404)
    
    # Check if file exists in storage
    try:
        report.file.open('rb')
        logger.info(f"File opened successfully: {report.file.name}")
    except Exception as e:
        logger.error(f"Error opening report file: {str(e)}", exc_info=True)
        return HttpResponse("Report file cannot be accessed", status=500)
    
    # Mark as downloaded
    report.mark_downloaded()
    logger.info(f"Download count incremented to {report.download_count}")
    
    # Prepare file response
    filename = f"{report.title.replace(' ', '_')}{report.get_file_extension()}"
    content_type = report.get_content_type()
    
    logger.info(f"Sending file as attachment - Filename: {filename}, Content-Type: {content_type}")
    
    response = FileResponse(
        report.file,
        content_type=content_type,
        as_attachment=True,
        filename=filename
    )
    
    # Close the file after response is sent
    response.close = report.file.close
    
    return response


@login_required
def report_list(request):
    """
    List all generated reports for the user.
    
    This view:
    1. Retrieves all reports for the current user
    2. Groups them by upload for better organization
    3. Orders by most recent first
    
    Template: reports/list.html
    """
    logger.info("=" * 50)
    logger.info("REPORT LIST VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    reports = GeneratedReport.objects.filter(user=request.user).order_by('-generated_at')
    logger.info(f"Found {reports.count()} total reports for user")
    
    # Group by upload for better organization
    upload_reports = {}
    for report in reports:
        upload_id = report.upload.id
        
        if upload_id not in upload_reports:
            upload_reports[upload_id] = {
                'upload': report.upload,
                'reports': []
            }
        upload_reports[upload_id]['reports'].append(report)
    
    logger.info(f"Grouped reports into {len(upload_reports)} upload categories")
    
    context = {
        'upload_reports': upload_reports,
        'active_tab': 'reports',
    }
    
    logger.info("Rendering report list template")
    return render(request, 'reports/list.html', context)


@login_required
def delete_report(request, report_id):
    """
    Delete a generated report.
    
    This view:
    1. Displays confirmation page (GET request)
    2. Deletes the report file and database record (POST request)
    
    Args:
        report_id: ID of the GeneratedReport to delete
        
    Template: reports/delete_confirm.html
    """
    logger.info("=" * 50)
    logger.info("DELETE REPORT VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}, Report ID: {report_id}")
    
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    logger.info(f"Report found: {report.title}")
    
    if request.method == 'POST':
        logger.info("Processing report deletion")
        
        # Delete file from storage
        if report.file:
            file_path = report.file.path if hasattr(report.file, 'path') else report.file.name
            logger.info(f"Deleting file: {file_path}")
            report.file.delete(save=False)
            logger.info("File deleted from storage")
        
        # Delete database record
        report.delete()
        logger.info("Report record deleted from database")
        
        logger.info("Redirecting to report list")
        return redirect('reports:report_list')
    
    logger.info("Displaying delete confirmation page")
    return render(request, 'reports/delete_confirm.html', {'report': report})


@login_required
def preview_report(request, report_id):
    """
    Preview report content in browser (for HTML reports).
    
    This view:
    1. Retrieves the specified report
    2. If HTML format, displays directly in browser
    3. Otherwise redirects to download
    
    Args:
        report_id: ID of the GeneratedReport to preview
        
    Template: reports/preview.html (fallback) or direct HTML
    """
    logger.info("=" * 50)
    logger.info("PREVIEW REPORT VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}, Report ID: {report_id}")
    
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    logger.info(f"Report found: {report.title}, Format: {report.format}")
    
    if report.format != 'html':
        logger.info(f"Report format is {report.format}, redirecting to download")
        return redirect('reports:download_report', report_id=report_id)
    
    # For HTML reports, we can display directly
    if report.file:
        logger.info("Reading HTML file content")
        try:
            with report.file.open('r') as f:
                html_content = f.read()
            
            content_length = len(html_content)
            logger.info(f"HTML content read successfully, length: {content_length} characters")
            
            return HttpResponse(html_content, content_type='text/html')
        except Exception as e:
            logger.error(f"Error reading HTML file: {str(e)}", exc_info=True)
            # Fall through to template preview
    
    # Fallback to template preview
    logger.info("Using template-based preview (fallback)")
    context = {
        'report': report,
        'report_data': report.report_data,
    }
    
    return render(request, 'reports/preview.html', context)