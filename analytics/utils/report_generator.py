# analytics/utils/report_generator.py
"""
Report generation utilities for creating downloadable reports
"""
from datetime import datetime
import json
import csv
import io
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import tempfile

class ReportGenerator:
    """
    Generates downloadable reports in various formats
    """
    
    def __init__(self, analysis, upload):
        self.analysis = analysis
        self.upload = upload
    
    def generate_pdf_report(self):
        """Generate PDF report using HTML template"""
        context = {
            'upload': self.upload,
            'analysis': self.analysis,
            'generated_at': datetime.now(),
            'top_ips': list(self.analysis.top_ips.items())[:10],
            'status_codes': self.analysis.status_codes,
            'suspicious_ips': self.analysis.suspicious_ips,
        }
        
        html_string = render_to_string('analytics/pdf_report.html', context)
        
        # Generate PDF
        pdf_file = HTML(string=html_string).write_pdf()
        
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="log_analysis_{self.upload.id}.pdf"'
        return response
    
    def generate_csv_report(self):
        """Generate CSV report with detailed entries"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'IP Address', 'Method', 'URL', 'Status Code', 'User Agent'])
        
        # Write entries
        entries = self.upload.entries.all().order_by('-timestamp')[:10000]  # Limit to 10k for performance
        for entry in entries:
            writer.writerow([
                entry.timestamp,
                entry.ip_address,
                entry.method or '',
                entry.url or '',
                entry.status_code or '',
                entry.user_agent or '',
            ])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="log_entries_{self.upload.id}.csv"'
        return response
    
    def generate_json_report(self):
        """Generate JSON report with analysis results"""
        report_data = {
            'upload_info': {
                'id': self.upload.id,
                'filename': str(self.upload.file.name),
                'log_type': self.upload.log_type,
                'uploaded_at': self.upload.uploaded_at.isoformat(),
            },
            'analysis': {
                'total_requests': self.analysis.total_requests,
                'unique_ips': self.analysis.unique_ips,
                'time_period_days': self.analysis.time_period_days,
                'avg_requests_per_day': self.analysis.avg_requests_per_day,
                'error_rate': self.analysis.error_rate,
                'top_ips': self.analysis.top_ips,
                'status_codes': self.analysis.status_codes,
                'top_endpoints': self.analysis.top_endpoints,
                'hourly_distribution': self.analysis.hourly_distribution,
                'daily_distribution': self.analysis.daily_distribution,
                'suspicious_ips': self.analysis.suspicious_ips,
            },
            'generated_at': datetime.now().isoformat(),
        }
        
        response = HttpResponse(json.dumps(report_data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="analysis_report_{self.upload.id}.json"'
        return response
