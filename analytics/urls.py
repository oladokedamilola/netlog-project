# analytics/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Single analytics page for each upload
    path('<int:upload_id>/', views.analytics_view, name='analytics_view'),
    
    # API endpoint for AJAX updates
    path('<int:upload_id>/chart-data/', views.chart_data_api, name='chart_data_api'),
    path('<int:upload_id>/check-processing-status/', views.check_processing_status, name='check_status'),
    
    
    # Main analytics dashboard
    path('', views.analytics_dashboard, name='dashboard'),
    path('api/chart-data/', views.dashboard_chart_data, name='dashboard_chart_data'),
    
    # Forensic search page and export functionality
    path('forensic-search/', views.forensic_search_view, name='forensic_search'),
    path('export-search-results/', views.export_search_results, name='export_search_results'),
]
