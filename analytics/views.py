from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from logs.models import LogUpload, ParsedEntry
from django.db.models import Count, Q
from django.db.models.functions import TruncHour, TruncDay
from django.utils import timezone

@login_required
def analytics_dashboard(request, upload_id):
    upload = get_object_or_404(LogUpload, id=upload_id, user=request.user)
    entries = ParsedEntry.objects.filter(upload=upload)

    # === Overview Metrics ===
    total_requests = entries.count()
    parsed_entries = total_requests
    total_errors = entries.filter(status_code__gte=400, status_code__lt=600).count()

    # === Traffic Data ===
    hourly_data = (
        entries.annotate(hour=TruncHour("timestamp"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    daily_data = (
        entries.annotate(day=TruncDay("timestamp"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    # Format for template consumption
    hourly_chart = [{"hour": item["hour"].isoformat(), "count": item["count"]} for item in hourly_data]
    daily_chart = [{"day": item["day"].date().isoformat(), "count": item["count"]} for item in daily_data]

    # === Status Codes ===
    status_codes_qs = (
        entries.values("status_code")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    status_codes = [{"status_code": sc["status_code"], "count": sc["count"]} for sc in status_codes_qs]

    # === Top IPs with suspicious detection ===
    top_ips_qs = (
        entries.values("ip_address")
        .annotate(
            requests_count=Count("id"),
            error_count=Count("id", filter=Q(status_code__gte=400, status_code__lt=600))
        )
        .order_by("-requests_count")[:10]
    )

    top_ips = []
    for ip in top_ips_qs:
        suspicious = ip["requests_count"] > 50 or (ip["error_count"]/max(ip["requests_count"],1)) > 0.3
        top_ips.append({
            "ip_address": ip["ip_address"],
            "requests_count": ip["requests_count"],
            "error_count": ip["error_count"],
            "suspicious": suspicious
        })

    # === Top Endpoints ===
    endpoints_qs = (
        entries.values("url")
        .annotate(
            requests_count=Count("id"),
            error_count=Count("id", filter=Q(status_code__gte=400))
        )
        .order_by("-requests_count")[:10]
    )
    endpoints = [{"url": ep["url"], "requests_count": ep["requests_count"], "error_count": ep["error_count"]} for ep in endpoints_qs]

    # === Error Spikes ===
    now = timezone.now()
    window_hours = 24
    current_start = now - timezone.timedelta(hours=window_hours)
    previous_start = current_start - timezone.timedelta(hours=window_hours)

    current_errors = entries.filter(timestamp__gte=current_start, timestamp__lte=now)\
                            .filter(Q(status_code__gte=400, status_code__lt=600)).count()
    previous_errors = entries.filter(timestamp__gte=previous_start, timestamp__lt=current_start)\
                             .filter(Q(status_code__gte=400, status_code__lt=600)).count()
    percent_change = 0
    if previous_errors == 0 and current_errors > 0:
        percent_change = 100
    elif previous_errors != 0:
        percent_change = ((current_errors - previous_errors)/previous_errors) * 100

    context = {
        "upload": upload,
        "total_requests": total_requests,
        "parsed_entries": parsed_entries,
        "total_errors": total_errors,
        "hourly_chart": hourly_chart,
        "daily_chart": daily_chart,
        "status_codes": status_codes,
        "top_ips": top_ips,
        "endpoints": endpoints,
        "current_errors": current_errors,
        "previous_errors": previous_errors,
        "percent_change": percent_change,
    }

    return render(request, "analytics/analytics.html", context)
