# accounts\rate_limit.py
from django.shortcuts import render
from django.contrib import messages
from .models import RateLimit

def handle_rate_limited_action(request, email, action, success_callback):
    """
    Decorator-like function to handle rate limited actions
    """
    is_allowed, block_info = RateLimit.check_rate_limit(email, action)
    
    if not is_allowed:
        # Render the rate limit exceeded page
        return render_rate_limit_page(request, action, block_info)
    
    # Execute the action
    result = success_callback()
    
    # If the action was successful, reset the rate limit counter
    if result:
        rate_limit = RateLimit.objects.get(email=email, action=action)
        rate_limit.reset_attempts()
    else:
        # If action failed, increment the counter
        rate_limit = RateLimit.objects.get(email=email, action=action)
        rate_limit.increment_attempt()
    
    return result

def render_rate_limit_page(request, action, block_info):
    """Render a friendly rate limit exceeded page"""
    context = {
        'action': action,
        'action_display': dict(RateLimit.ACTION_CHOICES).get(action, action),
        'minutes_remaining': block_info['minutes_remaining'],
        'blocked_until': block_info['blocked_until'],
        'attempts': block_info['attempts'],
    }
    return render(request, 'accounts/rate_limit_exceeded.html', context, status=429)

def increment_rate_limit(email, action):
    """Increment rate limit counter for an email/action"""
    try:
        rate_limit = RateLimit.objects.get(email=email, action=action)
        rate_limit.increment_attempt()
    except RateLimit.DoesNotExist:
        RateLimit.objects.create(
            email=email,
            action=action,
            attempt_count=1
        )

def reset_rate_limit(email, action):
    """Reset rate limit counter for an email/action"""
    try:
        rate_limit = RateLimit.objects.get(email=email, action=action)
        rate_limit.reset_attempts()
    except RateLimit.DoesNotExist:
        pass