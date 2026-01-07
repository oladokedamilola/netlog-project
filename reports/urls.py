# reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Report generation
    path('generate/', views.generate_report, name='generate_report'),
    path('quick/', views.quick_report, name='quick_report'),
    
    # Report management
    path('', views.report_list, name='report_list'),
    path('<int:report_id>/', views.report_detail, name='report_detail'),
    path('<int:report_id>/download/', views.download_report, name='download_report'),
    path('<int:report_id>/preview/', views.preview_report, name='preview_report'),
    path('<int:report_id>/delete/', views.delete_report, name='delete_report'),
]