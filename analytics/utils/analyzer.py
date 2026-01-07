# analytics/utils/analyzer.py
import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from django.utils import timezone
from django.db.models import Count, Q
import ipaddress

class LogAnalyzer:
    """
    Analyzes parsed log entries to generate insights and metrics
    """
    def __init__(self, upload):
        self.upload = upload
        self.entries = upload.entries.all()
    
    def analyze(self):
        """
        Perform comprehensive analysis on log entries
        Returns a dictionary with all analysis results
        """
        if not self.entries.exists():
            return self._empty_analysis()
        
        # Get basic metrics
        total_requests = self.entries.count()
        unique_ips = self.entries.values('ip_address').distinct().count()
        
        # Time analysis
        timestamps = self.entries.values_list('timestamp', flat=True).order_by('timestamp')
        if timestamps:
            first_date = timestamps.first()
            last_date = timestamps.last()
            time_period_days = (last_date - first_date).total_seconds() / (60 * 60 * 24)
            if time_period_days == 0:
                time_period_days = 1  # Avoid division by zero
            avg_requests_per_day = total_requests / time_period_days
        else:
            time_period_days = 0
            avg_requests_per_day = 0
        
        # Top IPs
        top_ips = dict(Counter(
            self.entries.values_list('ip_address', flat=True)
        ).most_common(20))
        
        # Status code distribution
        status_codes = dict(Counter(
            self.entries.exclude(status_code__isnull=True)
            .values_list('status_code', flat=True)
        ))
        
        # Group status codes into categories
        status_categories = defaultdict(int)
        for code, count in status_codes.items():
            if 200 <= code < 300:
                status_categories['2xx'] += count
            elif 300 <= code < 400:
                status_categories['3xx'] += count
            elif 400 <= code < 500:
                status_categories['4xx'] += count
            elif 500 <= code < 600:
                status_categories['5xx'] += count
        
        # Top endpoints (URLs)
        top_endpoints = dict(Counter(
            self.entries.exclude(url__isnull=True)
            .exclude(url='')
            .values_list('url', flat=True)
        ).most_common(20))
        
        # Top user agents
        top_user_agents = dict(Counter(
            self.entries.exclude(user_agent__isnull=True)
            .exclude(user_agent='')
            .values_list('user_agent', flat=True)
        ).most_common(10))
        
        # Hourly distribution (0-23)
        hourly_distribution = [0] * 24
        for entry in self.entries:
            if entry.timestamp:
                hour = entry.timestamp.hour
                hourly_distribution[hour] += 1
        
        # Daily distribution
        daily_distribution = defaultdict(int)
        for entry in self.entries:
            if entry.timestamp:
                date_str = entry.timestamp.date().isoformat()
                daily_distribution[date_str] += 1
        
        # Convert daily distribution to sorted list
        sorted_daily = dict(sorted(daily_distribution.items()))
        
        # Security analysis - suspicious IPs
        suspicious_ips = self._detect_suspicious_ips()
        
        # Error rate (4xx + 5xx)
        error_count = sum(
            count for code, count in status_codes.items()
            if 400 <= code < 600
        )
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'unique_ips': unique_ips,
            'time_period_days': time_period_days,
            'avg_requests_per_day': avg_requests_per_day,
            'top_ips': top_ips,
            'status_codes': status_categories,
            'top_endpoints': top_endpoints,
            'top_user_agents': top_user_agents,
            'hourly_distribution': hourly_distribution,
            'daily_distribution': sorted_daily,
            'suspicious_ips': suspicious_ips,
            'error_rate': error_rate,
        }
    
    def _detect_suspicious_ips(self):
        """
        Detect potentially suspicious IP addresses
        """
        suspicious_ips = []
        
        # 1. IPs with high error rates
        ip_errors = defaultdict(lambda: {'total': 0, 'errors': 0})
        
        for entry in self.entries:
            ip = entry.ip_address
            ip_errors[ip]['total'] += 1
            if entry.status_code and 400 <= entry.status_code < 600:
                ip_errors[ip]['errors'] += 1
        
        for ip, counts in ip_errors.items():
            if counts['total'] >= 10:  # Only consider IPs with enough requests
                error_rate = counts['errors'] / counts['total'] * 100
                if error_rate > 50:  # More than 50% error rate
                    suspicious_ips.append({
                        'ip': ip,
                        'reason': f'High error rate ({error_rate:.1f}%)',
                        'error_rate': error_rate,
                        'total_requests': counts['total'],
                        'error_requests': counts['errors']
                    })
        
        # 2. Private/internal IPs making requests (could be spoofed)
        for entry in self.entries:
            try:
                ip_obj = ipaddress.ip_address(entry.ip_address)
                if ip_obj.is_private and entry.ip_address not in [s['ip'] for s in suspicious_ips]:
                    suspicious_ips.append({
                        'ip': entry.ip_address,
                        'reason': 'Private/internal IP address',
                        'total_requests': 1
                    })
            except ValueError:
                continue
        
        # 3. IPs with suspicious patterns (e.g., sequential access to admin pages)
        admin_patterns = ['admin', 'login', 'wp-admin', 'phpmyadmin', 'config']
        ip_admin_access = defaultdict(int)
        
        for entry in self.entries:
            if entry.url:
                url_lower = entry.url.lower()
                if any(pattern in url_lower for pattern in admin_patterns):
                    ip_admin_access[entry.ip_address] += 1
        
        for ip, count in ip_admin_access.items():
            if count > 5 and ip not in [s['ip'] for s in suspicious_ips]:
                suspicious_ips.append({
                    'ip': ip,
                    'reason': f'Multiple admin page accesses ({count} times)',
                    'access_count': count
                })
        
        # Sort by severity
        suspicious_ips.sort(key=lambda x: x.get('error_rate', 0) or x.get('access_count', 0), reverse=True)
        return suspicious_ips[:10]  # Return top 10
    
    def _empty_analysis(self):
        """Return empty analysis structure when no entries exist"""
        return {
            'total_requests': 0,
            'unique_ips': 0,
            'time_period_days': 0,
            'avg_requests_per_day': 0,
            'top_ips': {},
            'status_codes': {},
            'top_endpoints': {},
            'top_user_agents': {},
            'hourly_distribution': [0] * 24,
            'daily_distribution': {},
            'suspicious_ips': [],
            'error_rate': 0,
        }
    
    def generate_report_text(self, analysis_data):
        """Generate human-readable report text"""
        report_lines = []
        
        report_lines.append(f"# Log Analysis Report")
        report_lines.append(f"## Summary")
        report_lines.append(f"- Total Requests: {analysis_data['total_requests']:,}")
        report_lines.append(f"- Unique IP Addresses: {analysis_data['unique_ips']}")
        report_lines.append(f"- Time Period: {analysis_data['time_period_days']:.1f} days")
        report_lines.append(f"- Average Daily Requests: {analysis_data['avg_requests_per_day']:.1f}")
        report_lines.append(f"- Error Rate: {analysis_data['error_rate']:.2f}%")
        
        if analysis_data['top_ips']:
            report_lines.append(f"\n## Top IP Addresses")
            for ip, count in list(analysis_data['top_ips'].items())[:5]:
                report_lines.append(f"- {ip}: {count:,} requests")
        
        if analysis_data['status_codes']:
            report_lines.append(f"\n## Status Code Distribution")
            for category, count in analysis_data['status_codes'].items():
                percentage = (count / analysis_data['total_requests'] * 100) if analysis_data['total_requests'] > 0 else 0
                report_lines.append(f"- {category}: {count:,} ({percentage:.1f}%)")
        
        if analysis_data['suspicious_ips']:
            report_lines.append(f"\n## Security Alerts")
            for suspicious in analysis_data['suspicious_ips'][:5]:
                report_lines.append(f"- {suspicious['ip']}: {suspicious['reason']}")
        
        return "\n".join(report_lines)