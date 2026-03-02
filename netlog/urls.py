from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from .views import home
from accounts.views import dashboard_view
from . import views 


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('logs/', include('logs.urls')),
    path('analytics/', include('analytics.urls')), 
    path('api/analytics/', include('analytics.urls')),
    path('reports/', include('reports.urls')),
    path('dashboard/', dashboard_view, name='dashboard'),
    
    path('terms/', views.TermsOfServiceView.as_view(), name='terms'),
    path('privacy/', views.PrivacyPolicyView.as_view(), name='privacy'),
]
from django.conf.urls import handler400, handler403, handler404, handler500

# Custom error handlers
handler400 = 'netlog.views.custom_bad_request'
handler403 = 'netlog.views.custom_permission_denied'
handler404 = 'netlog.views.custom_page_not_found'
handler500 = 'netlog.views.custom_server_error'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
