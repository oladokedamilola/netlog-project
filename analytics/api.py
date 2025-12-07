from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.db.models.functions import TruncHour, TruncDay
from django.utils import timezone
from datetime import datetime

from logs.models import ParsedEntry, LogUpload


# -------------------------
# Utility Helpers
# -------------------------
def parse_date_param(param):
    """Accepts '2025-12-07' or ISO '2025-12-07T00:00:00'."""
    if not param:
        return None
    try:
        return timezone.make_aware(datetime.fromisoformat(param))
    except Exception:
        return None


def get_filtered_queryset(request):
    """
    Filters records by:
    - upload_id (optional)
    - start (optional ISO datetime)
    - end (optional ISO datetime)

    MOST IMPORTANT:
    ❗ Ensures upload_id belongs to the requesting user.
    """
    qs = ParsedEntry.objects.all()

    upload_id = request.query_params.get('upload_id')
    start = parse_date_param(request.query_params.get('start'))
    end = parse_date_param(request.query_params.get('end'))

    if upload_id:
        try:
            upload_obj = LogUpload.objects.get(id=upload_id, user=request.user)
        except LogUpload.DoesNotExist:
            return ParsedEntry.objects.none()   # User not allowed
        qs = qs.filter(upload=upload_obj)

    else:
        # Restrict user to only their own logs even without upload_id
        qs = qs.filter(upload__user=request.user)

    if start:
        qs = qs.filter(timestamp__gte=start)
    if end:
        qs = qs.filter(timestamp__lte=end)

    return qs


# -------------------------
# 1. TOP IPs
# -------------------------
class TopIPsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        qs = get_filtered_queryset(request)

        data = list(
            qs.values('ip_address')
              .annotate(count=Count('id'))
              .order_by('-count')[:limit]
        )
        return Response({'top_ips': data})


# -------------------------
# 2. STATUS CODES
# -------------------------
class StatusCodesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = get_filtered_queryset(request)
        data = list(
            qs.values('status_code')
              .annotate(count=Count('id'))
              .order_by('-count')
        )
        return Response({'status_codes': data})


# -------------------------
# 3. HOURLY TRAFFIC PEAKS
# -------------------------
class TrafficPeaksHourlyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = get_filtered_queryset(request)

        # If no timeframe → default to last 24 hours
        if not request.query_params.get('start') and not request.query_params.get('end'):
            end = timezone.now()
            start = end - timezone.timedelta(hours=24)
            qs = qs.filter(timestamp__gte=start, timestamp__lte=end)

        hourly = qs.annotate(hour=TruncHour('timestamp')) \
                   .values('hour') \
                   .annotate(count=Count('id')) \
                   .order_by('hour')

        data = [{'hour': item['hour'].isoformat(), 'count': item['count']} for item in hourly]
        return Response({'hourly': data})


# -------------------------
# 4. DAILY TRAFFIC PEAKS
# -------------------------
class TrafficPeaksDailyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = get_filtered_queryset(request)

        # Default: past 30 days
        if not request.query_params.get('start') and not request.query_params.get('end'):
            end = timezone.now()
            start = end - timezone.timedelta(days=30)
            qs = qs.filter(timestamp__gte=start, timestamp__lte=end)

        daily = qs.annotate(day=TruncDay('timestamp')) \
                  .values('day') \
                  .annotate(count=Count('id')) \
                  .order_by('day')

        data = [{'day': item['day'].date().isoformat(), 'count': item['count']} for item in daily]
        return Response({'daily': data})


# -------------------------
# 5. ERROR SPIKES
# -------------------------
class ErrorSpikesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        window_hours = int(request.query_params.get('window_hours', 24))
        now = timezone.now()

        current_start = now - timezone.timedelta(hours=window_hours)
        prev_start = current_start - timezone.timedelta(hours=window_hours)

        qs = get_filtered_queryset(request)

        current_errors = qs.filter(timestamp__gte=current_start) \
                           .filter(Q(status_code__gte=400, status_code__lt=600)) \
                           .count()

        prev_errors = qs.filter(timestamp__gte=prev_start,
                                timestamp__lt=current_start) \
                         .filter(Q(status_code__gte=400, status_code__lt=600)) \
                         .count()

        if prev_errors == 0:
            change = 100.0 if current_errors > 0 else 0.0
        else:
            change = ((current_errors - prev_errors) / prev_errors) * 100.0

        return Response({
            'current_window': current_errors,
            'previous_window': prev_errors,
            'percent_change': change
        })


# -------------------------
# 6. TOP ENDPOINTS
# -------------------------
class TopEndpointsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        qs = get_filtered_queryset(request)

        endpoints = list(
            qs.values('url')
              .annotate(count=Count('id'))
              .order_by('-count')[:limit]
        )
        return Response({'top_endpoints': endpoints})
