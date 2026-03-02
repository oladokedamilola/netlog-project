from django.urls import path
from .views import (
    keep_alive, login_view, logout_view, register_view, 
    user_dashboard_view, admin_dashboard_view,
    verify_email_view, resend_verification_view, pending_verification_view,
    password_reset_request_view, password_reset_confirm_view,
    password_change_view,
    profile_view, profile_edit_view, profile_delete_confirm_view,
    profile_delete_view, profile_notifications_view, profile_security_view
)

urlpatterns = [
    # Authentication
    path('login/', login_view, name="login"),
    path('logout/', logout_view, name="logout"),
    path('register/', register_view, name="register"),
    
    # Dashboards
    path('dashboard/user/', user_dashboard_view, name="user_dashboard"),
    path('dashboard/admin/', admin_dashboard_view, name="admin_dashboard"),
    
    # Email verification
    path('verify-email/<str:token>/', verify_email_view, name="verify_email"),
    path('resend-verification/', resend_verification_view, name="resend_verification"),
    path('pending-verification/', pending_verification_view, name="pending_verification"), 
    
    # Password management
    path('reset-password/', password_reset_request_view, name="password_reset_request"),
    path('reset-password/confirm/<str:token>/', password_reset_confirm_view, name="password_reset_confirm"),
    path('change-password/', password_change_view, name="password_change"),
    
    # Profile management
    path('profile/', profile_view, name="profile"),
    path('profile/edit/', profile_edit_view, name="profile_edit"),
    path('profile/delete/confirm/', profile_delete_confirm_view, name="profile_delete_confirm"),
    path('profile/delete/', profile_delete_view, name="profile_delete"),
    path('profile/notifications/', profile_notifications_view, name="profile_notifications"),
    path('profile/security/', profile_security_view, name="profile_security"),
    
    path('keep-alive/', keep_alive, name='keep_alive'),
]