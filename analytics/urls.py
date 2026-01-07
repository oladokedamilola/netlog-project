# analytics/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Single analytics page for each upload
    path('<int:upload_id>/', views.analytics_view, name='analytics_view'),
    
    # Optional: API endpoint for AJAX updates if needed
    path('<int:upload_id>/chart-data/', views.chart_data_api, name='chart_data_api'),
]
