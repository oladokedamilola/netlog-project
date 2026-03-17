# accounts/utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

def send_verification_email(user, token):
    """Send email verification link to user"""
    verification_url = f"{settings.SITE_URL}/accounts/verify-email/{token}/"
    
    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': 'NetLog',
    }
    
    # Render email templates
    html_message = render_to_string('accounts/email/verification_email.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='Verify your email address - NetLog',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )

def send_password_reset_email(user, token):
    """Send password reset link to user"""
    reset_url = f"{settings.SITE_URL}/accounts/reset-password/confirm/{token}/"
    
    context = {
        'user': user,
        'reset_url': reset_url,
        'site_name': 'NetLog',
        'expiry_hours': getattr(settings, 'PASSWORD_RESET_TOKEN_EXPIRY_HOURS', 1),
    }
    
    # Render email templates
    html_message = render_to_string('accounts/email/password_reset_email.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='Reset your password - NetLog',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )