# reports/views.py
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

@login_required
def generate_report(request):
    """
    Main report generation view with form
    """
    if request.method == 'POST':
        form = ReportGenerationForm(request.user, request.POST)
        if form.is_valid():
            # Start timing
            start_time = time.time()
            
            # Get form data
            upload = form.cleaned_data['upload']
            report_type = form.cleaned_data['report_type']
            report_format = form.cleaned_data['format']
            title = form.cleaned_data['title']
            description = form.cleaned_data['description']
            
            # Get or create analysis
            from analytics.models import Analysis
            analysis, _ = Analysis.objects.get_or_create(
                upload=upload,
                defaults={'user': request.user}
            )
            
            # Apply date filters if specified
            entries = ParsedEntry.objects.filter(upload=upload)
            date_range = form.cleaned_data.get('date_range')
            
            if date_range == 'last7':
                cutoff = timezone.now() - timezone.timedelta(days=7)
                entries = entries.filter(timestamp__gte=cutoff)
            elif date_range == 'last30':
                cutoff = timezone.now() - timezone.timedelta(days=30)
                entries = entries.filter(timestamp__gte=cutoff)
            elif date_range == 'custom':
                start_date = form.cleaned_data.get('start_date')
                end_date = form.cleaned_data.get('end_date')
                if start_date and end_date:
                    entries = entries.filter(
                        timestamp__date__range=(start_date, end_date)
                    )
            
            # Generate report based on format
            report_data = {
                'title': title,
                'description': description,
                'report_type': report_type,
                'upload': upload,
                'analysis': analysis,
                'entries': entries,
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
            }
            
            # Generate the report file
            if report_format == 'pdf':
                file_content = generate_pdf_report(report_data)
                file_extension = '.pdf'
            elif report_format == 'csv':
                file_content = generate_csv_report(report_data)
                file_extension = '.csv'
            elif report_format == 'html':
                file_content = generate_html_report(report_data)
                file_extension = '.html'
            else:  # json
                file_content = generate_json_report(report_data)
                file_extension = '.json'
            
            # Create report record
            report = GeneratedReport.objects.create(
                user=request.user,
                upload=upload,
                report_type=report_type,
                format=report_format,
                title=title,
                description=description,
                report_data=report_data,
                generation_time=time.time() - start_time,
            )
            
            # Save file
            filename = f"report_{report.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}{file_extension}"
            report.file.save(filename, ContentFile(file_content))
            report.file_size = len(file_content)
            report.save()
            
            # Redirect to download page
            return redirect('reports:report_detail', report_id=report.id)
    else:
        form = ReportGenerationForm(request.user)
    
    # Get user's recent uploads for quick access
    recent_uploads = LogUpload.objects.filter(user=request.user).order_by('-uploaded_at')[:5]
    
    context = {
        'form': form,
        'recent_uploads': recent_uploads,
        'active_tab': 'generate',
    }
    return render(request, 'reports/generate.html', context)

@login_required
def quick_report(request):
    """
    Generate a quick report from analytics page
    """
    if request.method == 'POST':
        form = QuickReportForm(request.POST)
        if form.is_valid():
            upload = form.cleaned_data['upload']
            report_format = form.cleaned_data['format']
            
            # Generate a default title
            title = f"{upload.get_log_type_display()} Log Analysis - {timezone.now().strftime('%Y-%m-%d')}"
            
            # Get analysis
            from analytics.models import Analysis
            analysis, _ = Analysis.objects.get_or_create(
                upload=upload,
                defaults={'user': request.user}
            )
            
            # Create report data
            report_data = {
                'title': title,
                'description': f'Quick report generated from {upload.filename}',
                'report_type': 'summary',
                'upload': upload,
                'analysis': analysis,
                'entries': ParsedEntry.objects.filter(upload=upload)[:1000],  # Limit for quick report
                'generated_at': timezone.now(),
            }
            
            # Generate file
            if report_format == 'pdf':
                file_content = generate_pdf_report(report_data)
                file_extension = '.pdf'
            else:  # csv
                file_content = generate_csv_report(report_data)
                file_extension = '.csv'
            
            # Create report record
            report = GeneratedReport.objects.create(
                user=request.user,
                upload=upload,
                report_type='summary',
                format=report_format,
                title=title,
                report_data=report_data,
            )
            
            # Save file
            filename = f"quick_report_{report.id}{file_extension}"
            report.file.save(filename, ContentFile(file_content))
            report.file_size = len(file_content)
            report.save()
            
            return redirect('reports:download_report', report_id=report.id)
    
    return redirect('reports:generate_report')

@login_required
def report_detail(request, report_id):
    """View report details and download options"""
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    
    context = {
        'report': report,
        'active_tab': 'reports',
    }
    return render(request, 'reports/detail.html', context)

@login_required
def download_report(request, report_id):
    """Download generated report file"""
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    
    if not report.file:
        return HttpResponse("Report file not found", status=404)
    
    # Mark as downloaded
    report.mark_downloaded()
    
    # Prepare file response
    response = FileResponse(
        report.file.open('rb'),
        content_type=report.get_content_type(),
        as_attachment=True,
        filename=f"{report.title.replace(' ', '_')}{report.get_file_extension()}"
    )
    
    return response

@login_required
def report_list(request):
    """List all generated reports for the user"""
    reports = GeneratedReport.objects.filter(user=request.user).order_by('-generated_at')
    
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
    
    context = {
        'upload_reports': upload_reports,
        'active_tab': 'reports',
    }
    return render(request, 'reports/list.html', context)

@login_required
def delete_report(request, report_id):
    """Delete a generated report"""
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    
    if request.method == 'POST':
        # Delete file from storage
        if report.file:
            report.file.delete(save=False)
        
        # Delete database record
        report.delete()
        
        return redirect('reports:report_list')
    
    return render(request, 'reports/delete_confirm.html', {'report': report})

@login_required
def preview_report(request, report_id):
    """Preview report content in browser (for HTML reports)"""
    report = get_object_or_404(GeneratedReport, id=report_id, user=request.user)
    
    if report.format != 'html':
        return redirect('reports:download_report', report_id=report_id)
    
    # For HTML reports, we can display directly
    if report.file:
        with report.file.open('r') as f:
            html_content = f.read()
        
        return HttpResponse(html_content, content_type='text/html')
    
    # Fallback to template preview
    context = {
        'report': report,
        'report_data': report.report_data,
    }
    return render(request, 'reports/preview.html', context)