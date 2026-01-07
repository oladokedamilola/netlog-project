import json
import csv
import io
import logging
from datetime import datetime
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

# Try to import ReportLab
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch, cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available. Install with: pip install reportlab")

def generate_pdf_report(report_data):
    """
    Generate PDF report using ReportLab
    """
    if not REPORTLAB_AVAILABLE:
        logger.error("ReportLab is not available for PDF generation")
        return generate_fallback_text(report_data)
    
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1A1F36')
        )
        
        heading2_style = ParagraphStyle(
            'Heading2',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#1A1F36'),
            borderLeftWidth=4,
            borderLeftColor=colors.HexColor('#FF7A00'),
            borderLeftPadding=10,
            leftIndent=10
        )
        
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        # Title
        story.append(Paragraph(report_data['title'], title_style))
        
        # Generated timestamp and metadata
        metadata_text = f"""
        <para alignment="center">
        <font size="9" color="gray">
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} | 
        Report Type: {report_data.get('report_type', 'Summary').title()} | 
        Source: {report_data['upload'].filename if hasattr(report_data['upload'], 'filename') else 'Log File'}
        </font>
        </para>
        """
        story.append(Paragraph(metadata_text, normal_style))
        story.append(Spacer(1, 20))
        
        # Description (if available)
        if report_data.get('description'):
            story.append(Paragraph("Description", heading2_style))
            story.append(Paragraph(report_data['description'], normal_style))
            story.append(Spacer(1, 10))
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", heading2_style))
        
        analysis = report_data.get('analysis', {})
        if hasattr(analysis, 'total_requests'):
            total_requests = analysis.total_requests
            unique_ips = analysis.unique_ips
            error_rate = analysis.error_rate
            time_period = analysis.time_period_days
            avg_daily = analysis.avg_requests_per_day
        else:
            total_requests = analysis.get('total_requests', 0)
            unique_ips = analysis.get('unique_ips', 0)
            error_rate = analysis.get('error_rate', 0)
            time_period = analysis.get('time_period_days', 0)
            avg_daily = analysis.get('avg_requests_per_day', 0)
        
        # Summary metrics table
        summary_data = [
            ['Metric', 'Value', 'Insight'],
            ['Total Requests', f"{total_requests:,}", 
             'Excellent' if total_requests > 1000 else 'Good' if total_requests > 100 else 'Normal'],
            ['Unique IPs', f"{unique_ips:,}", 
             'High diversity' if unique_ips > 100 else 'Normal diversity'],
            ['Error Rate', f"{error_rate:.2f}%", 
             '⚠️ High' if error_rate > 10 else '✓ Normal' if error_rate > 5 else '✓ Excellent'],
            ['Time Period', f"{time_period:.1f} days", 
             f"Analyzed {time_period:.1f} days of data"],
            ['Avg Daily', f"{avg_daily:.1f}", 
             'High traffic' if avg_daily > 1000 else 'Normal traffic'],
        ]
        
        summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A1F36')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Key Insight
        insight_text = f"""
        <para>
        <b>Key Insight:</b> Your log analysis shows 
        {total_requests:,} total requests from {unique_ips:,} unique IP addresses. 
        The error rate is {error_rate:.2f}%, which is 
        {'high and requires attention' if error_rate > 10 else 'within acceptable limits'}.
        </para>
        """
        story.append(Paragraph(insight_text, normal_style))
        story.append(Spacer(1, 20))
        
        # Top IP Addresses
        story.append(Paragraph("Top IP Addresses", heading2_style))
        
        top_ips = analysis.top_ips if hasattr(analysis, 'top_ips') else analysis.get('top_ips', {})
        suspicious_ips = analysis.suspicious_ips if hasattr(analysis, 'suspicious_ips') else analysis.get('suspicious_ips', [])
        
        ip_data = [['Rank', 'IP Address', 'Requests', 'Percentage', 'Status']]
        for idx, (ip, count) in enumerate(list(top_ips.items())[:10], 1):
            percentage = (count / total_requests * 100) if total_requests > 0 else 0
            is_suspicious = any(s.get('ip') == ip for s in suspicious_ips) if suspicious_ips else False
            status = "⚠️ Suspicious" if is_suspicious else "✓ Normal"
            ip_data.append([str(idx), ip, f"{count:,}", f"{percentage:.1f}%", status])
        
        if len(ip_data) > 1:
            ip_table = Table(ip_data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 1*inch, 1*inch])
            ip_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (3, -1), 'CENTER'),
                ('TEXTCOLOR', (4, 1), (4, -1), 
                 colors.red if 'Suspicious' in ip_data[1][4] else colors.green),
            ]))
            story.append(ip_table)
        else:
            story.append(Paragraph("No IP data available", normal_style))
        
        story.append(Spacer(1, 20))
        
        # Status Code Distribution
        story.append(Paragraph("Status Code Distribution", heading2_style))
        
        status_codes = analysis.status_codes if hasattr(analysis, 'status_codes') else analysis.get('status_codes', {})
        
        status_data = [['Status', 'Count', 'Percentage']]
        for code, count in status_codes.items():
            percentage = (count / total_requests * 100) if total_requests > 0 else 0
            status_data.append([code, f"{count:,}", f"{percentage:.1f}%"])
        
        if len(status_data) > 1:
            status_table = Table(status_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch])
            status_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('ALIGN', (1, 1), (2, -1), 'CENTER'),
                ('TEXTCOLOR', (0, 1), (0, -1), 
                 colors.red if '4' in status_data[1][0] or '5' in status_data[1][0] 
                 else colors.green if '2' in status_data[1][0] 
                 else colors.blue),
            ]))
            story.append(status_table)
        else:
            story.append(Paragraph("No status code data available", normal_style))
        
        story.append(Spacer(1, 20))
        
        # Recommendations
        if report_data.get('options', {}).get('include_recommendations', True):
            story.append(PageBreak())
            story.append(Paragraph("Recommendations & Action Items", heading2_style))
            
            recommendations = [
                ("Monitor Error Rates", 
                 f"Current error rate is {error_rate:.2f}%. Set up alerts for error rates above 5%."),
                
                ("Review Suspicious IPs", 
                 f"{len(suspicious_ips) if suspicious_ips else 0} IP(s) flagged. Consider blocking or monitoring."),
                
                ("Optimize Performance", 
                 "Review server response times and optimize slow endpoints."),
                
                ("Security Hardening", 
                 "Implement rate limiting and review authentication logs."),
                
                ("Regular Analysis", 
                 "Schedule weekly log analysis to detect trends early."),
            ]
            
            for title, desc in recommendations:
                story.append(Paragraph(f"<b>• {title}:</b>", normal_style))
                story.append(Paragraph(f"  {desc}", ParagraphStyle('Indent', parent=normal_style, leftIndent=20)))
                story.append(Spacer(1, 8))
        
        # Footer/End note
        story.append(Spacer(1, 30))
        footer_text = f"""
        <para alignment="center">
        <font size="8" color="gray">
        Report generated by NetLog - Network Log Analyzer<br/>
        {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} | Page <page/>
        </font>
        </para>
        """
        story.append(Paragraph(footer_text, normal_style))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        return generate_fallback_text(report_data)

def generate_csv_report(report_data):
    """
    Generate CSV report with log data
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['NetLog - Log Analysis Report'])
    writer.writerow([f"Title: {report_data['title']}"])
    writer.writerow([f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    writer.writerow([])
    
    # Summary section
    writer.writerow(['SUMMARY METRICS'])
    writer.writerow(['Metric', 'Value'])
    
    analysis = report_data.get('analysis', {})
    if isinstance(analysis, dict):
        writer.writerow(['Total Requests', analysis.get('total_requests', 0)])
        writer.writerow(['Unique IPs', analysis.get('unique_ips', 0)])
        writer.writerow(['Error Rate', f"{analysis.get('error_rate', 0):.2f}%"])
        writer.writerow(['Time Period', f"{analysis.get('time_period_days', 0):.1f} days"])
        writer.writerow(['Avg Daily Requests', f"{analysis.get('avg_requests_per_day', 0):.1f}"])
    else:
        writer.writerow(['Total Requests', analysis.total_requests])
        writer.writerow(['Unique IPs', analysis.unique_ips])
        writer.writerow(['Error Rate', f"{analysis.error_rate:.2f}%"])
        writer.writerow(['Time Period', f"{analysis.time_period_days:.1f} days"])
        writer.writerow(['Avg Daily Requests', f"{analysis.avg_requests_per_day:.1f}"])
    
    writer.writerow([])
    
    # Top IPs section
    writer.writerow(['TOP IP ADDRESSES'])
    writer.writerow(['IP Address', 'Request Count', 'Percentage'])
    
    top_ips = analysis.top_ips if hasattr(analysis, 'top_ips') else analysis.get('top_ips', {})
    total_requests = analysis.total_requests if hasattr(analysis, 'total_requests') else analysis.get('total_requests', 1)
    
    for ip, count in list(top_ips.items())[:10]:
        percentage = (count / total_requests * 100) if total_requests > 0 else 0
        writer.writerow([ip, count, f"{percentage:.1f}%"])
    
    writer.writerow([])
    
    # Status codes section
    writer.writerow(['STATUS CODE DISTRIBUTION'])
    writer.writerow(['Status Code', 'Count', 'Percentage'])
    
    status_codes = analysis.status_codes if hasattr(analysis, 'status_codes') else analysis.get('status_codes', {})
    
    for code, count in status_codes.items():
        percentage = (count / total_requests * 100) if total_requests > 0 else 0
        writer.writerow([code, count, f"{percentage:.1f}%"])
    
    writer.writerow([])
    
    # Log entries
    writer.writerow(['LOG ENTRIES (Sample)'])
    writer.writerow(['Timestamp', 'IP Address', 'Method', 'URL', 'Status Code', 'User Agent'])
    
    entries = report_data.get('entries', [])[:100]
    for entry in entries:
        if hasattr(entry, 'timestamp'):
            timestamp = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S') if entry.timestamp else ''
            ip = entry.ip_address
            method = entry.method or ''
            url = (entry.url or '')[:100]
            status = entry.status_code or ''
            agent = (entry.user_agent or '')[:50]
        else:
            timestamp = entry.get('timestamp', '')
            ip = entry.get('ip_address', '')
            method = entry.get('method', '')
            url = entry.get('url', '')[:100]
            status = entry.get('status_code', '')
            agent = entry.get('user_agent', '')[:50]
        
        writer.writerow([timestamp, ip, method, url, status, agent])
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content.encode('utf-8')

def generate_html_report(report_data):
    """
    Generate HTML report for web viewing
    """
    context = {
        'report': report_data,
        'generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'include_summary': report_data['options'].get('include_summary', True),
        'include_charts': report_data['options'].get('include_charts', True),
        'include_top_data': report_data['options'].get('include_top_data', True),
        'include_recommendations': report_data['options'].get('include_recommendations', True),
    }
    
    html_string = render_to_string('reports/templates/html_report.html', context)
    return html_string.encode('utf-8')

def generate_json_report(report_data):
    """
    Generate JSON report with all data
    """
    # Convert complex objects to serializable format
    serializable_data = {
        'title': report_data['title'],
        'description': report_data.get('description', ''),
        'report_type': report_data['report_type'],
        'generated_at': timezone.now().isoformat(),
        
        'upload_info': {
            'filename': report_data['upload'].filename if hasattr(report_data['upload'], 'filename') else str(report_data['upload']),
            'log_type': report_data['upload'].log_type if hasattr(report_data['upload'], 'log_type') else 'unknown',
            'uploaded_at': report_data['upload'].uploaded_at.isoformat() if hasattr(report_data['upload'], 'uploaded_at') else '',
        },
        
        'analysis_summary': {
            'total_requests': report_data['analysis'].total_requests if hasattr(report_data['analysis'], 'total_requests') else report_data['analysis'].get('total_requests', 0),
            'unique_ips': report_data['analysis'].unique_ips if hasattr(report_data['analysis'], 'unique_ips') else report_data['analysis'].get('unique_ips', 0),
            'error_rate': report_data['analysis'].error_rate if hasattr(report_data['analysis'], 'error_rate') else report_data['analysis'].get('error_rate', 0),
            'time_period_days': report_data['analysis'].time_period_days if hasattr(report_data['analysis'], 'time_period_days') else report_data['analysis'].get('time_period_days', 0),
            'avg_requests_per_day': report_data['analysis'].avg_requests_per_day if hasattr(report_data['analysis'], 'avg_requests_per_day') else report_data['analysis'].get('avg_requests_per_day', 0),
        },
        
        'top_ips': report_data['analysis'].top_ips if hasattr(report_data['analysis'], 'top_ips') else report_data['analysis'].get('top_ips', {}),
        'status_codes': report_data['analysis'].status_codes if hasattr(report_data['analysis'], 'status_codes') else report_data['analysis'].get('status_codes', {}),
        'top_endpoints': report_data['analysis'].top_endpoints if hasattr(report_data['analysis'], 'top_endpoints') else report_data['analysis'].get('top_endpoints', {}),
        'suspicious_ips': report_data['analysis'].suspicious_ips if hasattr(report_data['analysis'], 'suspicious_ips') else report_data['analysis'].get('suspicious_ips', []),
        
        'generation_options': report_data.get('options', {}),
        'filters': report_data.get('filters', {}),
    }
    
    # Add log entries
    entries_list = []
    entries = report_data.get('entries', [])[:100]
    
    for entry in entries:
        if hasattr(entry, 'timestamp'):
            entries_list.append({
                'timestamp': entry.timestamp.isoformat() if entry.timestamp else None,
                'ip_address': entry.ip_address,
                'method': entry.method,
                'status_code': entry.status_code,
                'url': entry.url,
                'user_agent': entry.user_agent,
            })
        else:
            entries_list.append(entry)
    
    serializable_data['sample_entries'] = entries_list
    
    return json.dumps(serializable_data, indent=2).encode('utf-8')

def generate_fallback_text(report_data):
    """
    Generate a simple text report as fallback
    """
    analysis = report_data.get('analysis', {})
    if hasattr(analysis, 'total_requests'):
        total_requests = analysis.total_requests
        unique_ips = analysis.unique_ips
        error_rate = analysis.error_rate
    else:
        total_requests = analysis.get('total_requests', 0)
        unique_ips = analysis.get('unique_ips', 0)
        error_rate = analysis.get('error_rate', 0)
    
    text_report = f"""
{'='*60}
NETLOG - LOG ANALYSIS REPORT
{'='*60}

Title: {report_data['title']}
Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*60}
EXECUTIVE SUMMARY
{'='*60}

Total Requests: {total_requests:,}
Unique IP Addresses: {unique_ips:,}
Error Rate: {error_rate:.2f}%

{'='*60}
NOTE
{'='*60}

PDF generation requires ReportLab library.
Install it with: pip install reportlab

For now, you can generate CSV, HTML, or JSON reports.
"""
    return text_report.encode('utf-8')