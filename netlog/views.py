from django.shortcuts import render
from django.views.generic import TemplateView

import logging

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'home.html')


class TermsOfServiceView(TemplateView):
    """Display Terms of Service page"""
    template_name = 'terms.html'
    
    def get(self, request, *args, **kwargs):
        logger.info(f"Terms of Service page viewed - IP: {request.META.get('REMOTE_ADDR')}")
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'terms'
        return context


class PrivacyPolicyView(TemplateView):
    """Display Privacy Policy page"""
    template_name = 'privacy.html'
    
    def get(self, request, *args, **kwargs):
        logger.info(f"Privacy Policy page viewed - IP: {request.META.get('REMOTE_ADDR')}")
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'privacy'
        return context





def custom_page_not_found(request, exception):
    """Custom 404 error handler"""
    logger.warning(f"404 Not Found: {request.path} - Referrer: {request.META.get('HTTP_REFERER', 'None')}")
    return render(request, 'errors/404.html', status=404)

def custom_server_error(request):
    """Custom 500 error handler"""
    logger.error(f"500 Server Error: {request.path}")
    return render(request, 'errors/500.html', status=500)

def custom_permission_denied(request, exception):
    """Custom 403 error handler"""
    logger.warning(f"403 Forbidden: {request.path} - User: {request.user if request.user.is_authenticated else 'Anonymous'}")
    return render(request, 'errors/403.html', status=403)

def custom_bad_request(request, exception):
    """Custom 400 error handler"""
    logger.warning(f"400 Bad Request: {request.path}")
    return render(request, 'errors/400.html', status=400)

def custom_rate_limit(request, exception=None, retry_after=None):
    """Custom 429 rate limit error handler"""
    logger.warning(f"429 Too Many Requests: {request.path} - IP: {request.META.get('REMOTE_ADDR')}")
    context = {'retry_after': retry_after}
    return render(request, 'errors/429.html', context, status=429)

def custom_csrf_failure(request, reason=""):
    """Custom CSRF failure handler"""
    logger.warning(f"403 CSRF Failure: {request.path} - Reason: {reason}")
    return render(request, 'errors/403_csrf.html', {'reason': reason}, status=403)