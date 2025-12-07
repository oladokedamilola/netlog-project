from django.urls import path
from . import api

urlpatterns = [
    path('top-ips/', api.TopIPsView.as_view(), name='top_ips'),
    path('status-codes/', api.StatusCodesView.as_view(), name='status_codes'),
    path('traffic/hourly/', api.TrafficPeaksHourlyView.as_view(), name='traffic_hourly'),
    path('traffic/daily/', api.TrafficPeaksDailyView.as_view(), name='traffic_daily'),
    path('errors/spikes/', api.ErrorSpikesView.as_view(), name='error_spikes'),
    path('endpoints/top/', api.TopEndpointsView.as_view(), name='top_endpoints'),
]
