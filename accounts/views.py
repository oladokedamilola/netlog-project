# accounts/views.py
"""
Accounts App Views
=================
This module handles all authentication-related views including registration,
login, password management, profile management, and dashboard views.

Each view includes proper logging for monitoring and debugging purposes.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_not_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
import os
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
import smtplib

# Local application imports
from .forms import (
    RegisterForm, 
    PasswordResetRequestForm, 
    SetPasswordForm, 
    UserProfileForm, 
    ProfileSettingsForm
)
from .models import Profile, RateLimit
from .utils import send_verification_email, send_password_reset_email
from .rate_limit import increment_rate_limit, reset_rate_limit, render_rate_limit_page

# Import from other apps
from logs.models import LogUpload, ParsedEntry
from reports.models import GeneratedReport

import logging

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# REGISTRATION AND VERIFICATION VIEWS
# ============================================================================
@login_not_required
def register_view(request):
    """
    Handle user registration with comprehensive error handling and rate limiting.
    
    This view:
    1. Displays the registration form (GET request)
    2. Processes registration form submission (POST request)
    3. Creates a new user account (inactive until email verification)
    4. Sends verification email to the user
    5. Handles ALL errors gracefully with user-friendly messages
    6. Implements rate limiting to prevent abuse
    
    Template: accounts/register.html
    """
    logger.info("=" * 50)
    logger.info("REGISTER VIEW CALLED")
    logger.info("=" * 50)
    
    # Initialize form variable
    form = RegisterForm()
    
    if request.method == "POST":
        logger.info("--- Processing registration form submission ---")
        
        # Extract email for rate limiting
        email = request.POST.get('email', '').strip().lower()
        
        try:
            # Validate form data
            form = RegisterForm(request.POST)
            
            if form.is_valid():
                logger.info(f"Form is valid for email: {email}")
                
                # Check rate limit before proceeding
                is_allowed, block_info = RateLimit.check_rate_limit(email, 'registration')
                
                if not is_allowed:
                    logger.warning(f"Rate limit exceeded for registration: {email}")
                    return render_rate_limit_page(request, 'registration', block_info)
                
                # Attempt to create user account
                try:
                    user = form.save()
                    logger.info(f"User created successfully: {email} (ID: {user.id})")
                    
                except IntegrityError as e:
                    # Handle duplicate email (though form should catch this)
                    logger.error(f"Integrity error creating user {email}: {str(e)}", exc_info=True)
                    
                    # Increment rate limit counter for failed attempt
                    increment_rate_limit(email, 'registration')
                    
                    if 'email' in str(e).lower():
                        messages.error(
                            request,
                            "This email address is already registered. Please log in instead."
                        )
                    else:
                        messages.error(
                            request,
                            "We couldn't create your account due to a system conflict. Please try again."
                        )
                    return render(request, "accounts/register.html", {"form": form})
                    
                except DatabaseError as e:
                    # Database connection or query errors
                    logger.error(f"Database error creating user {email}: {str(e)}", exc_info=True)
                    
                    # Increment rate limit counter for failed attempt
                    increment_rate_limit(email, 'registration')
                    
                    messages.error(
                        request,
                        "We're experiencing technical difficulties. Please try again in a few minutes."
                    )
                    return render(request, "accounts/register.html", {"form": form})
                
                # Retrieve user profile
                try:
                    profile = Profile.objects.get(user=user)
                    logger.info(f"Profile retrieved for user: {email}")
                    
                except Profile.DoesNotExist:
                    logger.error(f"Profile not found for newly created user: {email}")
                    
                    # Attempt to create the profile manually
                    try:
                        profile = Profile.objects.create(user=user)
                        profile.generate_verification_token()
                        logger.info(f"Manually created profile for user: {email}")
                        
                    except Exception as e:
                        logger.error(f"Failed to create profile manually: {str(e)}", exc_info=True)
                        
                        # Clean up the orphaned user
                        try:
                            user.delete()
                            logger.info(f"Deleted orphaned user: {email}")
                        except:
                            pass
                        
                        # Increment rate limit counter for failed attempt
                        increment_rate_limit(email, 'registration')
                        
                        messages.error(
                            request,
                            "There was a problem setting up your account. Please contact support."
                        )
                        return render(request, "accounts/register.html", {"form": form})
                
                # Send verification email
                try:
                    logger.info(f"Attempting to send verification email to: {email}")
                    send_verification_email(user, profile.email_verification_token)
                    logger.info("Verification email sent successfully")
                    
                    # Reset rate limit on successful registration
                    reset_rate_limit(email, 'registration')
                    
                    # Success! Redirect to login with friendly message
                    messages.success(
                        request, 
                        f"Thank you for registering! We've sent a verification link to **{email}**."
                    )
                    messages.info(
                        request, 
                        "Please check your inbox (and spam folder) and click the link to activate your account."
                    )
                    
                    # Store email in session for potential resend functionality
                    request.session['pending_verification_email'] = email
                    
                    return redirect("login")
                    
                except (ConnectionRefusedError, smtplib.SMTPException) as e:
                    # Email server connection issues
                    logger.error(f"Email server error for {email}: {str(e)}", exc_info=True)
                    
                    # Clean up the user since we can't verify them
                    try:
                        user.delete()
                        logger.info(f"Deleted user {email} due to email server failure")
                    except:
                        pass
                    
                    # Increment rate limit counter for failed attempt
                    increment_rate_limit(email, 'registration')
                    
                    messages.error(
                        request,
                        "We're having trouble with our email system right now. Please try again in a few minutes."
                    )
                    return redirect("register")
                    
                except TimeoutError as e:
                    # Email sending timeout
                    logger.error(f"Email sending timeout for {email}: {str(e)}", exc_info=True)
                    
                    # Clean up the user
                    try:
                        user.delete()
                        logger.info(f"Deleted user {email} due to email timeout")
                    except:
                        pass
                    
                    # Increment rate limit counter for failed attempt
                    increment_rate_limit(email, 'registration')
                    
                    messages.error(
                        request,
                        "The verification email timed out. Please try again."
                    )
                    return redirect("register")
                    
                except Exception as e:
                    # Catch-all for any other email-related errors
                    logger.error(f"Unexpected error sending verification email to {email}: {str(e)}", exc_info=True)
                    
                    # Clean up the user
                    try:
                        user.delete()
                        logger.info(f"Deleted user {email} due to unexpected email error")
                    except:
                        pass
                    
                    # Increment rate limit counter for failed attempt
                    increment_rate_limit(email, 'registration')
                    
                    messages.error(
                        request,
                        "We couldn't complete your registration due to a technical issue. Please try again later."
                    )
                    return redirect("register")
            
            else:
                # Form is invalid - increment rate limit for failed validation
                increment_rate_limit(email, 'registration')
                
                # Show user-friendly messages without technical details
                logger.warning(f"Registration form validation failed for email: {email}")
                
                # Handle specific form errors with user-friendly messages
                for field, errors in form.errors.items():
                    for error in errors:
                        logger.warning(f"Field '{field}': {error}")
                        
                        # Map technical errors to user-friendly messages
                        if field == 'email':
                            if 'already exists' in error:
                                messages.error(
                                    request,
                                    "This email address is already registered. Please log in or use a different email."
                                )
                            elif 'valid' in error.lower():
                                messages.error(
                                    request,
                                    "Please enter a valid email address."
                                )
                            else:
                                messages.error(request, f"Email: {error}")
                        
                        elif field == 'password1':
                            if 'too short' in error.lower() or '8 characters' in error.lower():
                                messages.error(
                                    request,
                                    "Your password must be at least 8 characters long."
                                )
                            elif 'common' in error.lower():
                                messages.error(
                                    request,
                                    "Your password is too common. Please choose a stronger password."
                                )
                            elif 'entirely numeric' in error.lower():
                                messages.error(
                                    request,
                                    "Your password can't be entirely numbers. Please include letters or symbols."
                                )
                            else:
                                messages.error(request, f"Password: {error}")
                        
                        elif field == 'password2':
                            if 'match' in error.lower():
                                messages.error(
                                    request,
                                    "The passwords you entered don't match. Please try again."
                                )
                            else:
                                messages.error(request, f"Password confirmation: {error}")
                        
                        else:
                            # Generic fallback for unexpected fields
                            messages.error(request, f"Please check your {field} and try again.")
                
                # Add a helpful hint
                messages.info(
                    request,
                    "Need help? Make sure your email is correct and your password is strong enough."
                )
        
        except RateLimit.DoesNotExist:
            # This shouldn't happen as get_or_create handles it, but just in case
            logger.error(f"RateLimit record error for {email}")
            
        except ValidationError as e:
            # Django validation errors
            logger.error(f"Validation error in registration for {email}: {str(e)}", exc_info=True)
            increment_rate_limit(email, 'registration')
            messages.error(
                request,
                "Some of the information you provided wasn't valid. Please check and try again."
            )
            
        except DatabaseError as e:
            # General database errors
            logger.error(f"Database error in registration for {email}: {str(e)}", exc_info=True)
            increment_rate_limit(email, 'registration')
            messages.error(
                request,
                "We're experiencing technical difficulties. Please try again in a few minutes."
            )
            
        except ConnectionError as e:
            # Network/connection errors
            logger.error(f"Connection error in registration for {email}: {str(e)}", exc_info=True)
            increment_rate_limit(email, 'registration')
            messages.error(
                request,
                "Network connection issue detected. Please check your internet and try again."
            )
            
        except MemoryError as e:
            # System resource errors
            logger.error(f"Memory error in registration: {str(e)}", exc_info=True)
            increment_rate_limit(email, 'registration')
            messages.error(
                request,
                "The system is currently under high load. Please try again later."
            )
            
        except Exception as e:
            # Catch-all for any other unexpected errors
            logger.error(f"UNEXPECTED ERROR in registration for {email}: {str(e)}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}")
            
            # Log the full traceback for debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Increment rate limit counter for unexpected errors (prevents abuse)
            try:
                increment_rate_limit(email, 'registration')
            except:
                pass
            
            messages.error(
                request,
                "An unexpected error occurred. Our team has been notified and is working on it."
            )
    
    else:
        # GET request - display empty form
        logger.info("Displaying empty registration form")
        form = RegisterForm()
    
    # Always return the rendered template
    return render(request, "accounts/register.html", {"form": form})


@login_not_required
def verify_email_view(request, token):
    """
    Verify user's email address and log them in automatically.
    
    This view:
    1. Validates the verification token
    2. Activates the user account if token is valid
    3. Logs the user in automatically
    4. Redirects to appropriate dashboard based on user role
    
    Args:
        token: The email verification token sent to user's email
        
    Template: No template - redirects to dashboard or login
    """
    logger.info("=" * 50)
    logger.info("EMAIL VERIFICATION ATTEMPT")
    logger.info("=" * 50)
    logger.info(f"Token received: {token}")
    
    try:
        # Find profile with this token
        profile = Profile.objects.get(email_verification_token=token)
        logger.info(f"Profile found for user: {profile.user.username}")
        logger.info(f"Token created at: {profile.token_created_at}")
        logger.info(f"Token valid: {profile.is_token_valid()}")
        
        # Check if token is valid and not expired
        if profile.is_token_valid():
            logger.info("Token is valid, proceeding with verification")
            
            # Update profile verification status
            profile.email_verified = True
            profile.email_verification_token = None  # Clear token after use
            profile.token_created_at = None
            profile.save()
            logger.info("Profile updated: email_verified=True, token cleared")
            
            # Activate the user account
            user = profile.user
            user.is_active = True
            user.save()
            logger.info(f"User {user.username} activated (is_active=True)")
            
            # Reset rate limit for this email
            reset_rate_limit(user.email, 'email_verification')
            logger.info(f"Rate limit reset for: {user.email}")
            
            logger.info(f"User {user.username} successfully verified")
            
            # Automatically log the user in
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            logger.info(f"User {user.username} automatically logged in")
            
            messages.success(
                request, 
                "Your email has been verified successfully! You are now logged in."
            )
            
            # Check for next URL in session (if any)
            next_url = request.session.pop('next_url', None)
            if next_url:
                logger.info(f"Redirecting to next URL from session: {next_url}")
                return redirect(next_url)
            
            # Check if user is a superuser
            if user.is_superuser:
                logger.info("Redirecting to admin panel")
                messages.info(request, "Welcome! Redirecting to admin panel...")
                return redirect("admin:index")
            else:
                logger.info("Redirecting to dashboard")
                messages.info(request, "Welcome to NetLog! Your account is now fully activated.")
                return redirect("dashboard")
            
        else:
            # Token expired or invalid
            logger.warning(f"Token expired or invalid. Created at: {profile.token_created_at}")
            messages.error(
                request, 
                "The verification link is invalid or has expired. Please request a new one."
            )
            return redirect("resend_verification")
            
    except Profile.DoesNotExist:
        logger.error(f"No profile found with token: {token}")
        
        # Check if there's a user with this email in session
        pending_email = request.session.get('pending_verification_email')
        if pending_email:
            logger.info(f"Found pending email in session: {pending_email}")
            try:
                user = User.objects.get(email=pending_email, is_active=False)
                profile = Profile.objects.get(user=user)
                logger.info(f"Found inactive user: {user.username}")
                logger.info(f"Current token in profile: {profile.email_verification_token}")
                
                messages.error(
                    request, 
                    "The verification link is invalid. A new verification email has been sent."
                )
                
                # Generate and send new token
                new_token = profile.generate_verification_token()
                logger.info(f"Generated new token for {user.email}")
                send_verification_email(user, new_token)
                logger.info("New verification email sent")
                
                return redirect('pending_verification')
                
            except (User.DoesNotExist, Profile.DoesNotExist):
                logger.error(f"No inactive user found with session email: {pending_email}")
        
        messages.error(request, "Invalid verification link. Please request a new one.")
        return redirect("resend_verification")
    
    except Exception as e:
        logger.error(f"Unexpected error in email verification: {str(e)}", exc_info=True)
        messages.error(request, "An error occurred during verification. Please try again.")
        return redirect("resend_verification")


@login_not_required
def resend_verification_view(request):
    """
    Resend verification email with rate limiting.
    
    This view:
    1. Takes email address from POST request
    2. Checks rate limit for this email
    3. Resends verification email if account exists and is inactive
    4. Provides generic success message for security
    
    Template: accounts/resend_verification.html
    """
    logger.info("=" * 50)
    logger.info("RESEND VERIFICATION VIEW CALLED")
    logger.info("=" * 50)
    
    if request.method == "POST":
        email = request.POST.get("email")
        logger.info(f"Resend verification requested for email: {email}")
        
        # Check rate limit
        is_allowed, block_info = RateLimit.check_rate_limit(email, 'email_verification')
        logger.info(f"Rate limit check - allowed: {is_allowed}, block_info: {block_info}")
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for email: {email}")
            return render_rate_limit_page(request, 'email_verification', block_info)
        
        try:
            user = User.objects.get(email=email, is_active=False)
            logger.info(f"Found inactive user: {user.username}")
            profile = Profile.objects.get(user=user)
            
            # Generate new token
            profile.generate_verification_token()
            logger.info(f"Generated new verification token for {email}")
            
            # Resend verification email
            send_verification_email(user, profile.email_verification_token)
            logger.info(f"Verification email resent to {email}")
            
            # Reset rate limit on success
            reset_rate_limit(email, 'email_verification')
            logger.info(f"Rate limit reset for {email}")
            
            messages.success(
                request, 
                "A new verification email has been sent. Please check your inbox."
            )
            
        except User.DoesNotExist:
            # Increment rate limit for failed attempt (security - don't reveal if email exists)
            logger.warning(f"No inactive user found with email: {email}")
            increment_rate_limit(email, 'email_verification')
            logger.info(f"Rate limit incremented for {email}")
            
            # Generic message for security
            messages.success(
                request, 
                "A new verification email has been sent. Please check your inbox."
            )
            
        except Exception as e:
            logger.error(f"Error resending verification email: {str(e)}", exc_info=True)
            increment_rate_limit(email, 'email_verification')
            messages.error(
                request, 
                "There was an error sending the verification email. Please try again."
            )
    
    return render(request, "accounts/resend_verification.html")


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

@login_not_required
def login_view(request):
    """
    Handle user login with email/username and password.
    
    This view:
    1. Displays login form (GET request)
    2. Processes login credentials (POST request)
    3. Supports login with either username or email
    4. Handles unverified email cases
    5. Implements "Remember Me" functionality
    6. Redirects to appropriate dashboard based on user role
    
    Template: accounts/login.html
    """
    logger.info("=" * 50)
    logger.info("LOGIN VIEW CALLED")
    logger.info("=" * 50)
    
    # Get the next URL from query parameters
    next_url = request.GET.get('next')
    if next_url:
        logger.info(f"Next URL parameter found: {next_url}")
        request.session['next_url'] = next_url
    
    if request.method == "POST":
        logger.info("--- POST Request Received ---")
        username_or_email = request.POST.get("username")
        password = request.POST.get("password")
        remember_me = request.POST.get("remember_me")  # This will be 'on' or None
        
        logger.info(f"Username/Email input: {username_or_email}")
        logger.info(f"Password provided: {'Yes' if password else 'No'}")
        logger.info(f"Remember me: {remember_me}")

        # Check if fields are empty
        if not username_or_email or not password:
            logger.warning("Empty fields detected")
            messages.warning(request, "Please enter both email and password.")
            return render(request, "accounts/login.html", {'next': next_url})

        # Determine if input is email or username
        is_email = '@' in username_or_email
        logger.info(f"Is email format: {is_email}")
        
        # Try to find user by email or username
        try:
            logger.info(f"Looking up user by {'email' if is_email else 'username'}")
            if is_email:
                user = User.objects.get(email=username_or_email)
                logger.info(f"User found by email: {user.username}")
            else:
                user = User.objects.get(username=username_or_email)
                logger.info(f"User found by username: {user.username}")
            
            # Check user status
            logger.info(f"User is_active: {user.is_active}")
            logger.info(f"User email: {user.email}")
            
            # Check if email exists but is not verified
            if not user.is_active:
                logger.info("User is inactive, handling verification flow")
                
                # Get or create profile
                profile, created = Profile.objects.get_or_create(user=user)
                logger.info(f"Profile exists: {not created}")
                logger.info(f"Current email_verified: {profile.email_verified}")
                
                # Generate new verification token
                logger.info("Generating new verification token")
                token = profile.generate_verification_token()
                logger.info(f"Token generated: {token[:20]}...")
                logger.info(f"Token created at: {profile.token_created_at}")
                
                # Resend verification email
                logger.info("Attempting to send verification email")
                try:
                    logger.info(f"Sending to: {user.email}")
                    logger.info(f"From: {settings.DEFAULT_FROM_EMAIL}")
                    logger.info(f"Using backend: {settings.EMAIL_BACKEND}")
                    
                    send_verification_email(user, token)
                    logger.info("Verification email sent successfully!")
                    
                    # Store email in session for the pending verification page
                    request.session['pending_verification_email'] = user.email
                    logger.info(f"Stored email in session: {user.email}")
                    
                    # Redirect to pending verification page
                    logger.info("Redirecting to pending verification page")
                    return redirect('pending_verification')
                    
                except Exception as e:
                    logger.error("EMAIL SENDING FAILED", exc_info=True)
                    logger.error(f"Error type: {type(e).__name__}")
                    logger.error(f"Error message: {str(e)}")
                    
                    # Log email configuration for debugging
                    logger.error("--- Email Configuration Check ---")
                    logger.error(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
                    logger.error(f"EMAIL_HOST: {settings.EMAIL_HOST}")
                    logger.error(f"EMAIL_PORT: {settings.EMAIL_PORT}")
                    logger.error(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
                    logger.error(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
                    logger.error(f"EMAIL_HOST_PASSWORD set: {'Yes' if settings.EMAIL_HOST_PASSWORD else 'No'}")
                    logger.error(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
                    logger.error(f"SITE_URL: {settings.SITE_URL}")
                    
                    messages.error(
                        request, 
                        "Unable to send verification email. Please try again later or contact support."
                    )
                    return render(request, "accounts/login.html", {'next': next_url})
            
        except User.DoesNotExist:
            logger.info(f"No user found with {'email' if is_email else 'username'}: {username_or_email}")
            # Continue to authentication attempt - will fail with generic message

        # Attempt authentication
        logger.info("Attempting authentication")
        user = authenticate(request, username=username_or_email, password=password)
        
        if user is not None:
            logger.info(f"Authentication successful for user: {user.username}")
            logger.info(f"User is_active: {user.is_active}")
            logger.info(f"User is_superuser: {user.is_superuser}")
            logger.info(f"User is_staff: {user.is_staff}")
            
            # Check rate limit for successful login
            if is_email:
                reset_rate_limit(username_or_email, 'login')
                logger.info(f"Rate limit reset for: {username_or_email}")
            
            # Perform login
            login(request, user)
            logger.info("User logged in successfully")
            
            # Handle session expiry based on remember me
            if remember_me == 'on':  # Checkbox returns 'on' when checked
                # If "Remember Me" is checked, set session to last 30 days
                request.session.set_expiry(2592000)  # 30 days in seconds
                logger.info("Session set to 30 days (remember me enabled)")
                messages.info(request, "You'll stay logged in for 30 days.")
            else:
                # Use default session expiry from settings (24 hours)
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
                logger.info(f"Session set to {settings.SESSION_COOKIE_AGE} seconds (default)")
            
            messages.success(request, f"Welcome back, {user.username}!")
            
            # Check for next URL (in this order: POST parameter, session, GET parameter)
            redirect_to = (
                request.POST.get('next') or 
                request.session.pop('next_url', None) or 
                request.GET.get('next')
            )
            
            if redirect_to:
                logger.info(f"Redirecting to next URL: {redirect_to}")
                return redirect(redirect_to)
            
            # Check if user is a superuser
            if user.is_superuser:
                logger.info("Redirecting to admin panel")
                messages.info(request, "Redirecting to admin panel...")
                return redirect("admin:index")
            else:
                logger.info("Redirecting to dashboard")
                return redirect("dashboard")
        else:
            logger.warning(f"Authentication failed for: {username_or_email}")
            
            # Increment rate limit for failed login (only if email was provided)
            if is_email:
                increment_rate_limit(username_or_email, 'login')
                logger.info(f"Rate limit incremented for: {username_or_email}")
            
            messages.error(request, "Invalid email or password. Please try again.")
            return render(request, "accounts/login.html", {'next': next_url})

    logger.info("Rendering login page (GET request)")
    return render(request, "accounts/login.html", {'next': next_url})


@login_not_required
def pending_verification_view(request):
    """
    Show page informing user that their email is pending verification.
    
    This view:
    1. Displays pending verification page
    2. Allows user to request a new verification email
    3. Allows user to change email address
    
    Template: accounts/pending_verification.html
    """
    logger.info("=" * 50)
    logger.info("PENDING VERIFICATION VIEW CALLED")
    logger.info("=" * 50)
    
    email = request.session.get('pending_verification_email')
    logger.info(f"Email from session: {email}")
    
    if not email:
        # If no email in session, redirect to login
        logger.warning("No email in session, redirecting to login")
        return redirect('login')
    
    if request.method == "POST":
        # Handle resend verification request
        action = request.POST.get('action')
        logger.info(f"POST action received: {action}")
        
        if action == 'resend':
            try:
                user = User.objects.get(email=email, is_active=False)
                profile = Profile.objects.get(user=user)
                logger.info(f"Found inactive user: {user.username}")
                
                # Check rate limit
                is_allowed, block_info = RateLimit.check_rate_limit(email, 'email_verification')
                logger.info(f"Rate limit check - allowed: {is_allowed}")
                
                if not is_allowed:
                    logger.warning(f"Rate limit exceeded for {email}")
                    messages.error(
                        request, 
                        f"Too many attempts. Please wait {block_info['minutes_remaining']} minutes."
                    )
                    return render(request, "accounts/pending_verification.html", {'email': email})
                
                # Generate new token and send email
                token = profile.generate_verification_token()
                logger.info(f"Generated new token for {email}")
                send_verification_email(user, token)
                logger.info(f"Verification email resent to {email}")
                
                messages.success(request, "A new verification email has been sent. Please check your inbox.")
                
            except (User.DoesNotExist, Profile.DoesNotExist):
                logger.error(f"Account not found for email: {email}")
                messages.error(request, "Account not found. Please register again.")
                return redirect('register')
        
        elif action == 'change_email':
            # Clear session and redirect to register to use different email
            logger.info(f"User requested to change email from: {email}")
            del request.session['pending_verification_email']
            return redirect('register')
    
    return render(request, "accounts/pending_verification.html", {'email': email})


def logout_view(request):
    """
    Log out the current user.
    
    This view:
    1. Logs out the user
    2. Displays success message
    3. Redirects to login page
    
    Template: No template - redirects to login
    """
    logger.info("=" * 50)
    logger.info("LOGOUT VIEW CALLED")
    logger.info("=" * 50)
    
    username = request.user.username if request.user.is_authenticated else "Guest"
    logger.info(f"Logging out user: {username}")
    
    logout(request)
    logger.info("User logged out successfully")
    
    messages.success(request, f"You have been logged out successfully. Goodbye, {username}!")
    messages.info(request, "Hope to see you again soon!")
    
    return redirect("login")


# ============================================================================
# PASSWORD MANAGEMENT VIEWS
# ============================================================================

@login_not_required
def password_reset_request_view(request):
    """
    Request password reset email with rate limiting.
    
    This view:
    1. Displays password reset request form (GET)
    2. Processes email submission (POST)
    3. Sends reset email if account exists
    4. Implements rate limiting
    5. Provides generic success message for security
    
    Template: accounts/password_reset_request.html
    """
    logger.info("=" * 50)
    logger.info("PASSWORD RESET REQUEST VIEW CALLED")
    logger.info("=" * 50)
    
    if request.method == "POST":
        logger.info("Processing password reset request form")
        form = PasswordResetRequestForm(request.POST)
        
        if form.is_valid():
            email = form.cleaned_data['email']
            logger.info(f"Password reset requested for email: {email}")
            
            # Check rate limit
            is_allowed, block_info = RateLimit.check_rate_limit(email, 'password_reset')
            logger.info(f"Rate limit check - allowed: {is_allowed}")
            
            if not is_allowed:
                logger.warning(f"Rate limit exceeded for password reset: {email}")
                return render_rate_limit_page(request, 'password_reset', block_info)
            
            try:
                user = User.objects.get(email=email, is_active=True)
                logger.info(f"Found active user: {user.username}")
                profile = Profile.objects.get(user=user)
                
                # Generate reset token
                token = profile.generate_password_reset_token()
                logger.info(f"Generated password reset token for {email}")
                
                # Send reset email
                try:
                    send_password_reset_email(user, token)
                    logger.info(f"Password reset email sent to {email}")
                    
                    # Reset rate limit on success
                    reset_rate_limit(email, 'password_reset')
                    logger.info(f"Rate limit reset for {email}")
                    
                    messages.success(
                        request, 
                        "Password reset instructions have been sent to your email."
                    )
                    messages.info(
                        request, 
                        "Please check your inbox and follow the link to reset your password."
                    )
                    return redirect("login")
                    
                except Exception as e:
                    logger.error(f"Failed to send password reset email: {str(e)}", exc_info=True)
                    
                    # Increment rate limit for failed attempt
                    increment_rate_limit(email, 'password_reset')
                    logger.info(f"Rate limit incremented for {email}")
                    
                    messages.error(
                        request, 
                        "There was an error sending the reset email. Please try again."
                    )
                    profile.clear_password_reset_token()  # Clear the token if email fails
                    logger.info("Cleared password reset token due to email failure")
                    
            except User.DoesNotExist:
                # Increment rate limit for failed attempt (don't reveal if email exists)
                logger.info(f"No active user found with email: {email}")
                increment_rate_limit(email, 'password_reset')
                logger.info(f"Rate limit incremented for {email}")
                
                # Don't reveal that the email doesn't exist (security)
                messages.success(
                    request, 
                    "If an account exists with this email, you'll receive reset instructions."
                )
                return redirect("login")
    else:
        logger.info("Displaying password reset request form")
        form = PasswordResetRequestForm()
    
    return render(request, "accounts/password_reset_request.html", {"form": form})


@login_not_required
def password_reset_confirm_view(request, token):
    """
    Confirm password reset and set new password.
    
    This view:
    1. Validates reset token
    2. Displays new password form (GET)
    3. Sets new password (POST)
    4. Clears reset token after use
    
    Args:
        token: Password reset token sent to user's email
        
    Template: accounts/password_reset_confirm.html
    """
    logger.info("=" * 50)
    logger.info("PASSWORD RESET CONFIRM VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"Token received: {token}")
    
    # Find profile with this token
    try:
        profile = Profile.objects.get(password_reset_token=token)
        logger.info(f"Profile found for user: {profile.user.username}")
        
        # Check if token is valid
        if not profile.is_password_reset_token_valid():
            logger.warning(f"Password reset token expired for user: {profile.user.username}")
            messages.error(request, "The password reset link has expired. Please request a new one.")
            return redirect("password_reset_request")
            
    except Profile.DoesNotExist:
        logger.error(f"No profile found with password reset token: {token}")
        messages.error(request, "Invalid password reset link.")
        return redirect("password_reset_request")
    
    if request.method == "POST":
        logger.info("Processing password reset form submission")
        form = SetPasswordForm(request.POST)
        
        if form.is_valid():
            user = profile.user
            new_password = form.cleaned_data['new_password1']
            
            # Set new password
            user.set_password(new_password)
            user.save()
            logger.info(f"Password reset successfully for user: {user.username}")
            
            # Clear the reset token
            profile.clear_password_reset_token()
            logger.info("Password reset token cleared")
            
            # Reset rate limit for this email
            reset_rate_limit(user.email, 'password_reset')
            logger.info(f"Rate limit reset for {user.email}")
            
            messages.success(request, "Your password has been reset successfully!")
            messages.info(request, "You can now log in with your new password.")
            return redirect("login")
        else:
            logger.warning("Password reset form is invalid")
            for field, errors in form.errors.items():
                for error in errors:
                    logger.warning(f"Password error: {error}")
                    messages.error(request, f"{error}")
    else:
        logger.info("Displaying password reset confirmation form")
        form = SetPasswordForm()
    
    return render(request, "accounts/password_reset_confirm.html", {
        "form": form,
        "validlink": True,
        "username": profile.user.username
    })


@login_required
def password_change_view(request):
    """
    Allow logged-in users to change their password.
    
    This view:
    1. Displays password change form (GET)
    2. Processes password change (POST)
    3. Updates session auth hash to keep user logged in
    
    Template: accounts/password_change.html
    """
    logger.info("=" * 50)
    logger.info("PASSWORD CHANGE VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    if request.method == "POST":
        logger.info("Processing password change form submission")
        form = PasswordChangeForm(request.user, request.POST)
        
        if form.is_valid():
            user = form.save()
            # Keep the user logged in
            update_session_auth_hash(request, user)
            logger.info(f"Password changed successfully for user: {user.username}")
            
            messages.success(request, "Your password was successfully changed!")
            return redirect("dashboard")
        else:
            logger.warning("Password change form is invalid")
            for field, errors in form.errors.items():
                for error in errors:
                    logger.warning(f"Password change error: {error}")
                    messages.error(request, f"{error}")
    else:
        logger.info("Displaying password change form")
        form = PasswordChangeForm(request.user)
    
    return render(request, "accounts/password_change.html", {"form": form})


# ============================================================================
# DASHBOARD VIEWS
# ============================================================================

@login_required
def dashboard_view(request):
    """
    Main dashboard view that redirects users to their role-specific dashboard.
    
    This view:
    1. Checks user role (admin/superuser vs regular user)
    2. Redirects to appropriate dashboard
    
    Template: No template - redirects to role-specific dashboard
    """
    logger.info("=" * 50)
    logger.info("DASHBOARD VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}, Superuser: {request.user.is_superuser}, Staff: {request.user.is_staff}")
    
    if request.user.is_superuser or request.user.is_staff:
        logger.info("Redirecting to admin dashboard")
        return redirect('admin_dashboard')
    else:
        logger.info("Redirecting to user dashboard")
        return redirect('user_dashboard')


@login_required
def user_dashboard_view(request):
    """
    Regular user dashboard showing their logs, reports, and analytics.
    
    This view:
    1. Fetches user's recent logs and reports
    2. Calculates statistics
    3. Compiles recent activity feed
    
    Template: accounts/user_dashboard.html
    """
    logger.info("=" * 50)
    logger.info("USER DASHBOARD VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    user = request.user
    
    # Get user's recent logs
    recent_logs = LogUpload.objects.filter(
        user=user
    ).order_by('-uploaded_at')[:5]
    logger.info(f"Found {recent_logs.count()} recent logs")
    
    # Get user's recent reports
    recent_reports = GeneratedReport.objects.filter(
        user=user
    ).order_by('-generated_at')[:5]
    logger.info(f"Found {recent_reports.count()} recent reports")
    
    # Calculate statistics
    total_logs = LogUpload.objects.filter(user=user).count()
    total_reports = GeneratedReport.objects.filter(user=user).count()
    logger.info(f"Total logs: {total_logs}, Total reports: {total_reports}")
    
    # Logs uploaded this week
    week_ago = timezone.now() - timedelta(days=7)
    logs_this_week = LogUpload.objects.filter(
        user=user,
        uploaded_at__gte=week_ago
    ).count()
    logger.info(f"Logs this week: {logs_this_week}")
    
    # Recent activity (combined logs and reports)
    recent_activity = []
    
    # Add recent logs to activity
    for log in recent_logs:
        recent_activity.append({
            'type': 'log',
            'icon': 'fa-file-lines',
            'title': os.path.basename(log.file.name) if log.file else 'Unknown log',
            'description': f"Log file • {log.get_log_type_display()}",
            'time': log.uploaded_at,
            'url': f"/logs/{log.id}/"  # Update this with actual URL if available
        })
    
    # Add recent reports to activity
    for report in recent_reports:
        recent_activity.append({
            'type': 'report',
            'icon': 'fa-chart-simple',
            'title': report.title,
            'description': f"Report • {report.get_format_display()}",
            'time': report.generated_at,
            'url': report.get_absolute_url() if hasattr(report, 'get_absolute_url') else '#'
        })
    
    # Sort activity by time (most recent first)
    recent_activity.sort(key=lambda x: x['time'], reverse=True)
    recent_activity = recent_activity[:8]  # Show only 8 most recent
    logger.info(f"Compiled {len(recent_activity)} recent activity items")
    
    context = {
        'recent_logs': recent_logs,
        'recent_reports': recent_reports,
        'total_logs': total_logs,
        'total_reports': total_reports,
        'logs_this_week': logs_this_week,
        'recent_activity': recent_activity,
        'page_title': 'My Dashboard',
    }
    
    return render(request, 'accounts/user_dashboard.html', context)


@login_required
@staff_member_required
def admin_dashboard_view(request):
    """
    Admin dashboard showing system-wide statistics and management tools.
    
    This view:
    1. Fetches system-wide statistics
    2. Monitors rate limiting
    3. Shows recent activity across all users
    4. Prepares chart data for visualizations
    
    Template: accounts/admin_dashboard.html
    """
    logger.info("=" * 50)
    logger.info("ADMIN DASHBOARD VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"Admin user: {request.user.username}")
    
    # System statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    verified_users = Profile.objects.filter(email_verified=True).count()
    logger.info(f"System stats - Total users: {total_users}, Active: {active_users}, Verified: {verified_users}")
    
    # Log statistics
    total_logs = LogUpload.objects.count()
    logs_today = LogUpload.objects.filter(
        uploaded_at__date=timezone.now().date()
    ).count()
    logs_this_week = LogUpload.objects.filter(
        uploaded_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    logger.info(f"Log stats - Total: {total_logs}, Today: {logs_today}, This week: {logs_this_week}")
    
    # Report statistics
    total_reports = GeneratedReport.objects.count()
    reports_this_week = GeneratedReport.objects.filter(
        generated_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    logger.info(f"Report stats - Total: {total_reports}, This week: {reports_this_week}")
    
    # Rate limit monitoring
    blocked_ips = RateLimit.objects.filter(
        blocked_until__gt=timezone.now()
    ).count()
    logger.info(f"Blocked IPs: {blocked_ips}")
    
    # Recent users
    recent_users = User.objects.order_by('-date_joined')[:5]
    logger.info(f"Recent users: {[user.username for user in recent_users]}")
    
    # Top uploaders
    top_uploaders = User.objects.annotate(
        log_count=Count('uploads')  # Using the related_name from LogUpload model
    ).order_by('-log_count')[:5]
    
    # Recent activity (system-wide)
    recent_activity = []
    
    # New user registrations
    for user in recent_users:
        recent_activity.append({
            'type': 'user',
            'icon': 'fa-user-plus',
            'title': f"New user: {user.username}",
            'description': user.email,
            'time': user.date_joined,
            'url': f"/admin/auth/user/{user.id}/"
        })
    
    # Recent log uploads
    recent_logs = LogUpload.objects.select_related('user').order_by('-uploaded_at')[:5]
    for log in recent_logs:
        recent_activity.append({
            'type': 'log',
            'icon': 'fa-upload',
            'title': f"Log uploaded: {os.path.basename(log.file.name) if log.file else 'Unknown'}",
            'description': f"by {log.user.username}",
            'time': log.uploaded_at,
            'url': f"/admin/logs/logupload/{log.id}/change/"
        })
    
    # Sort activity
    recent_activity.sort(key=lambda x: x['time'], reverse=True)
    recent_activity = recent_activity[:8]
    logger.info(f"Compiled {len(recent_activity)} recent activity items")
    
    # Chart data (last 7 days)
    last_7_days = [(timezone.now() - timedelta(days=i)).date() for i in range(6, -1, -1)]
    
    daily_logs = []
    daily_users = []
    
    for day in last_7_days:
        # Logs per day
        log_count = LogUpload.objects.filter(
            uploaded_at__date=day
        ).count()
        daily_logs.append(log_count)
        
        # New users per day
        user_count = User.objects.filter(
            date_joined__date=day
        ).count()
        daily_users.append(user_count)
    
    logger.info(f"Chart data prepared - Logs: {daily_logs}, Users: {daily_users}")
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'verified_users': verified_users,
        'total_logs': total_logs,
        'logs_today': logs_today,
        'logs_this_week': logs_this_week,
        'total_reports': total_reports,
        'reports_this_week': reports_this_week,
        'blocked_ips': blocked_ips,
        'recent_users': recent_users,
        'top_uploaders': top_uploaders,
        'recent_activity': recent_activity,
        'daily_logs': daily_logs,
        'daily_users': daily_users,
        'last_7_days': [day.strftime('%a') for day in last_7_days],
        'page_title': 'Admin Dashboard',
    }
    
    return render(request, 'accounts/admin_dashboard.html', context)


# ============================================================================
# PROFILE MANAGEMENT VIEWS
# ============================================================================

@login_required
def profile_view(request):
    """
    View user profile information.
    
    This view:
    1. Displays user profile data
    2. Shows user statistics (logs, reports)
    3. Shows recent activity
    
    Template: accounts/profile.html
    """
    logger.info("=" * 50)
    logger.info("PROFILE VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    user = request.user
    profile = user.profile
    
    # Get user statistics
    total_logs = LogUpload.objects.filter(user=user).count()
    total_reports = GeneratedReport.objects.filter(user=user).count()
    logger.info(f"User stats - Logs: {total_logs}, Reports: {total_reports}")
    
    # Get recent activity
    recent_logs = LogUpload.objects.filter(user=user).order_by('-uploaded_at')[:3]
    recent_reports = GeneratedReport.objects.filter(user=user).order_by('-generated_at')[:3]
    
    # Account age
    account_age_days = (timezone.now() - user.date_joined).days
    logger.info(f"Account age: {account_age_days} days")
    
    context = {
        'user': user,
        'profile': profile,
        'total_logs': total_logs,
        'total_reports': total_reports,
        'recent_logs': recent_logs,
        'recent_reports': recent_reports,
        'account_age_days': account_age_days,
        'page_title': 'My Profile',
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit_view(request):
    """
    Edit user profile information.
    
    This view:
    1. Displays profile edit form with current data (GET)
    2. Processes profile updates (POST)
    3. Updates both User and Profile models
    
    Template: accounts/profile_edit.html
    """
    logger.info("=" * 50)
    logger.info("PROFILE EDIT VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        logger.info("Processing profile edit form submission")
        user_form = UserProfileForm(request.POST, instance=user)
        profile_form = ProfileSettingsForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            # Save user information
            user_form.save()
            logger.info(f"User information updated for: {user.username}")
            
            # Save profile information
            profile_form.save()
            logger.info("Profile information updated")
            
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('profile')
        else:
            logger.warning("Profile edit form is invalid")
            if not user_form.is_valid():
                logger.warning(f"User form errors: {user_form.errors}")
            if not profile_form.is_valid():
                logger.warning(f"Profile form errors: {profile_form.errors}")
            messages.error(request, "Please correct the errors below.")
    else:
        logger.info("Displaying profile edit form")
        user_form = UserProfileForm(instance=user)
        profile_form = ProfileSettingsForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'page_title': 'Edit Profile',
    }
    
    return render(request, 'accounts/profile_edit.html', context)


@login_required
def profile_delete_confirm_view(request):
    """
    Confirm account deletion.
    
    This view:
    1. Displays confirmation page before account deletion
    
    Template: accounts/profile_delete_confirm.html
    """
    logger.info("=" * 50)
    logger.info("PROFILE DELETE CONFIRM VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User requesting deletion: {request.user.username}")
    
    return render(request, 'accounts/profile_delete_confirm.html')


@login_required
def profile_delete_view(request):
    """
    Delete user account permanently.
    
    This view:
    1. Verifies password and confirmation
    2. Permanently deletes user account and all related data
    3. Logs out the user
    
    Template: No template - redirects after processing
    """
    logger.info("=" * 50)
    logger.info("PROFILE DELETE VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User attempting deletion: {request.user.username}")
    
    if request.method == 'POST':
        confirm = request.POST.get('confirm')
        password = request.POST.get('password')
        logger.info(f"Confirmation text provided: {confirm}")
        
        # Verify password
        user = authenticate(username=request.user.username, password=password)
        
        if user is not None and confirm == 'DELETE':
            # Store username for message
            username = user.username
            logger.info(f"Account deletion confirmed for user: {username}")
            
            # Delete user (cascade will delete profile and related data)
            user.delete()
            logger.info(f"User account permanently deleted: {username}")
            
            messages.success(
                request, 
                f"Your account '{username}' has been permanently deleted. We're sorry to see you go!"
            )
            return redirect('home')
        else:
            if confirm != 'DELETE':
                logger.warning(f"Incorrect confirmation text: {confirm}")
                messages.error(request, "Please type 'DELETE' to confirm.")
            else:
                logger.warning("Incorrect password provided for account deletion")
                messages.error(request, "Incorrect password. Please try again.")
            
            return redirect('profile_delete_confirm')
    
    logger.warning("Non-POST request to profile_delete_view, redirecting")
    return redirect('profile')


@login_required
def profile_notifications_view(request):
    """
    Notification settings (placeholder for future implementation).
    
    Template: accounts/profile_notifications.html
    """
    logger.info("=" * 50)
    logger.info("PROFILE NOTIFICATIONS VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    context = {
        'page_title': 'Notification Settings',
    }
    return render(request, 'accounts/profile_notifications.html', context)


@login_required
def profile_security_view(request):
    """
    Security settings page.
    
    Template: accounts/profile_security.html
    """
    logger.info("=" * 50)
    logger.info("PROFILE SECURITY VIEW CALLED")
    logger.info("=" * 50)
    logger.info(f"User: {request.user.username}")
    
    context = {
        'user': request.user,
        'page_title': 'Security Settings',
    }
    return render(request, 'accounts/profile_security.html', context)


# ============================================================================
# UTILITY VIEWS
# ============================================================================

@login_required
def keep_alive(request):
    """
    Simple endpoint to keep session alive.
    
    This view:
    1. Returns JSON response to indicate session is active
    2. Used by frontend to prevent session timeout
    
    Returns: JsonResponse with status 'ok'
    """
    logger.debug(f"Keep-alive ping from user: {request.user.username}")
    return JsonResponse({'status': 'ok'})