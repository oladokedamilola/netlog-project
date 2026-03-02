from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

class SessionTimeoutMiddleware:
    """
    Middleware to handle session expiration and show user-friendly messages
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if user was logged in but session expired
        if not request.user.is_authenticated and request.session.get('_auth_user_id'):
            # Session expired - user was logged in but now isn't
            logger.info(f"Session expired for user ID: {request.session.get('_auth_user_id')}")
            
            # Clear the stale session
            request.session.flush()
            
            # Add flash message for the next request
            messages.info(request, 
                "Your session has expired due to inactivity. "
                "Please log in again to continue using NetLog."
            )
            
            # Store the page they were trying to access
            request.session['next_url'] = request.path
        
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Check for session expiry before processing protected views
        """
        # List of URLs that don't require authentication
        exempt_urls = [
            reverse('login'),
            reverse('register'),
            reverse('password_reset_request'),
            reverse('password_reset_confirm', kwargs={'token': 'dummy'}),
        ]
        
        # Check if the requested URL requires authentication
        if request.user.is_authenticated:
            # Update session expiry on each request if SAVE_EVERY_REQUEST is True
            # This is handled automatically by Django
            pass
        elif not any(request.path.startswith(url) for url in exempt_urls):
            # User is trying to access a protected page without being authenticated
            # Check if this is due to session expiry
            if request.session.get('_auth_user_id'):
                messages.warning(request,
                    "Your session has expired. Please log in again to continue."
                )
                return redirect(f"{reverse('login')}?next={request.path}")