# accounts/admin.py
"""
Accounts App Admin Configuration
===============================
This module configures the Django admin interface for the accounts app models.

It provides customized admin views for managing user profiles and rate limiting,
with enhanced list displays, filters, search capabilities, and inline editing.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Q
import logging

from .models import Profile, RateLimit

# Set up logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# PROFILE ADMIN
# ============================================================================

class ProfileInline(admin.StackedInline):
    """
    Inline admin for Profile model to display within User admin.
    
    This allows editing profile information directly on the User admin page.
    """
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fieldsets = (
        ('Account Status', {
            'fields': ('email_verified', 'created_at'),
            'classes': ('wide',),
        }),
        ('Verification Tokens', {
            'fields': ('email_verification_token', 'token_created_at'),
            'classes': ('wide', 'collapse'),
        }),
        ('Password Reset', {
            'fields': ('password_reset_token', 'password_reset_token_created_at'),
            'classes': ('wide', 'collapse'),
        }),
        ('Additional Information', {
            'fields': ('organization',),
            'classes': ('wide',),
        }),
    )
    readonly_fields = ('created_at', 'token_created_at', 'password_reset_token_created_at')


class CustomUserAdmin(UserAdmin):
    """
    Customized User admin with Profile inline and enhanced list display.
    
    Adds profile information to the user list view and provides
    additional filtering and search capabilities.
    """
    
    # Add profile fields to list display
    list_display = ('username', 'email', 'first_name', 'last_name', 
                    'is_active', 'is_staff', 'get_email_verified', 
                    'get_organization', 'date_joined')
    
    list_filter = UserAdmin.list_filter + ('profile__email_verified', 'profile__organization')
    
    search_fields = UserAdmin.search_fields + ('profile__organization',)
    
    inlines = [ProfileInline]
    
    # Add custom actions
    actions = ['verify_emails', 'unverify_emails', 'send_verification_emails']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Profile Information', {
            'fields': (),
            'classes': ('wide',),
        }),
    )
    
    def get_email_verified(self, obj):
        """Display email verification status with colored icon"""
        if hasattr(obj, 'profile') and obj.profile.email_verified:
            return format_html(
                '<span style="color: green;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color: orange;">○ Pending</span>'
        )
    get_email_verified.short_description = 'Email Verified'
    get_email_verified.admin_order_field = 'profile__email_verified'
    
    def get_organization(self, obj):
        """Display user's organization"""
        if hasattr(obj, 'profile') and obj.profile.organization:
            return obj.profile.organization
        return '-'
    get_organization.short_description = 'Organization'
    get_organization.admin_order_field = 'profile__organization'
    
    def verify_emails(self, request, queryset):
        """Admin action to verify selected users' emails"""
        count = 0
        for user in queryset:
            profile, created = Profile.objects.get_or_create(user=user)
            if not profile.email_verified:
                profile.email_verified = True
                profile.email_verification_token = None
                profile.token_created_at = None
                profile.save()
                count += 1
        
        self.message_user(request, f"{count} user(s) email verified successfully.")
        logger.info(f"Admin {request.user.username} verified emails for {count} users")
    verify_emails.short_description = "Verify selected users' emails"
    
    def unverify_emails(self, request, queryset):
        """Admin action to unverify selected users' emails"""
        count = 0
        for user in queryset:
            profile, created = Profile.objects.get_or_create(user=user)
            if profile.email_verified:
                profile.email_verified = False
                profile.save()
                count += 1
        
        self.message_user(request, f"{count} user(s) email unverified.")
        logger.info(f"Admin {request.user.username} unverified emails for {count} users")
    unverify_emails.short_description = "Unverify selected users' emails"
    
    def send_verification_emails(self, request, queryset):
        """Admin action to send verification emails to selected users"""
        from .utils import send_verification_email
        
        success_count = 0
        error_count = 0
        
        for user in queryset:
            try:
                profile, created = Profile.objects.get_or_create(user=user)
                token = profile.generate_verification_token()
                send_verification_email(user, token)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        
        self.message_user(
            request, 
            f"Verification emails sent to {success_count} user(s). "
            f"Failed: {error_count}"
        )
        logger.info(f"Admin {request.user.username} sent verification emails to {success_count} users")
    send_verification_emails.short_description = "Send verification emails"


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin configuration for Profile model.
    
    Provides comprehensive management of user profiles including
    verification status, tokens, and organization information.
    """
    
    list_display = ('user', 'organization', 'email_verified', 
                   'token_status', 'reset_token_status', 'created_at')
    
    list_filter = ('email_verified', 'organization', 'created_at')
    
    search_fields = ('user__username', 'user__email', 'organization')
    
    readonly_fields = ('created_at', 'token_created_at', 'password_reset_token_created_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'organization'),
            'classes': ('wide',),
        }),
        ('Email Verification', {
            'fields': ('email_verified', 'email_verification_token', 'token_created_at'),
            'classes': ('wide', 'collapse'),
        }),
        ('Password Reset', {
            'fields': ('password_reset_token', 'password_reset_token_created_at'),
            'classes': ('wide', 'collapse'),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    actions = ['verify_emails', 'unverify_emails', 'clear_tokens']
    
    def token_status(self, obj):
        """Display token validity status with color coding"""
        if obj.email_verification_token:
            if obj.is_token_valid():
                return format_html(
                    '<span style="color: green;">✓ Valid</span>'
                )
            else:
                return format_html(
                    '<span style="color: red;">✗ Expired</span>'
                )
        return format_html(
            '<span style="color: gray;">— No token</span>'
        )
    token_status.short_description = 'Verification Token'
    
    def reset_token_status(self, obj):
        """Display password reset token validity status"""
        if obj.password_reset_token:
            if obj.is_password_reset_token_valid():
                return format_html(
                    '<span style="color: green;">✓ Valid</span>'
                )
            else:
                return format_html(
                    '<span style="color: red;">✗ Expired</span>'
                )
        return format_html(
            '<span style="color: gray;">— No token</span>'
        )
    reset_token_status.short_description = 'Reset Token'
    
    def verify_emails(self, request, queryset):
        """Admin action to verify selected profiles"""
        updated = queryset.update(
            email_verified=True,
            email_verification_token=None,
            token_created_at=None
        )
        self.message_user(request, f"{updated} profile(s) email verified.")
        logger.info(f"Admin {request.user.username} verified emails for {updated} profiles")
    verify_emails.short_description = "Verify selected profiles"
    
    def unverify_emails(self, request, queryset):
        """Admin action to unverify selected profiles"""
        updated = queryset.update(email_verified=False)
        self.message_user(request, f"{updated} profile(s) email unverified.")
        logger.info(f"Admin {request.user.username} unverified emails for {updated} profiles")
    unverify_emails.short_description = "Unverify selected profiles"
    
    def clear_tokens(self, request, queryset):
        """Admin action to clear verification and reset tokens"""
        updated = queryset.update(
            email_verification_token=None,
            token_created_at=None,
            password_reset_token=None,
            password_reset_token_created_at=None
        )
        self.message_user(request, f"Tokens cleared for {updated} profile(s).")
        logger.info(f"Admin {request.user.username} cleared tokens for {updated} profiles")
    clear_tokens.short_description = "Clear all tokens"


# ============================================================================
# RATE LIMIT ADMIN
# ============================================================================

@admin.register(RateLimit)
class RateLimitAdmin(admin.ModelAdmin):
    """
    Admin configuration for RateLimit model.
    
    Provides monitoring and management of rate limiting across
    different actions (login, password reset, email verification, etc.).
    """
    
    list_display = ('email', 'action', 'attempt_count', 
                   'first_attempt_at', 'last_attempt_at', 
                   'blocked_status', 'time_remaining')
    
    list_filter = ('action', 'blocked_until', 'first_attempt_at')
    
    search_fields = ('email',)
    
    readonly_fields = ('first_attempt_at', 'last_attempt_at')
    
    fieldsets = (
        ('Rate Limit Information', {
            'fields': ('email', 'action', 'attempt_count'),
            'classes': ('wide',),
        }),
        ('Timing Information', {
            'fields': ('first_attempt_at', 'last_attempt_at', 'blocked_until'),
            'classes': ('wide',),
        }),
    )
    
    actions = ['reset_attempts', 'block_selected', 'unblock_selected']
    
    def blocked_status(self, obj):
        """Display blocked status with color coding"""
        if obj.is_blocked():
            return format_html(
                '<span style="color: red; font-weight: bold;">🔒 Blocked</span>'
            )
        elif obj.attempt_count >= 3:
            return format_html(
                '<span style="color: orange;">⚠ At limit</span>'
            )
        elif obj.attempt_count > 0:
            return format_html(
                '<span style="color: blue;">{}/3 attempts</span>'.format(obj.attempt_count)
            )
        else:
            return format_html(
                '<span style="color: green;">✓ Clear</span>'
            )
    blocked_status.short_description = 'Status'
    blocked_status.admin_order_field = 'blocked_until'
    
    def time_remaining(self, obj):
        """Display time remaining if blocked"""
        if obj.is_blocked():
            remaining = obj.blocked_until - timezone.now()
            minutes = int(remaining.total_seconds() / 60)
            seconds = int(remaining.total_seconds() % 60)
            return f"{minutes}m {seconds}s"
        return '-'
    time_remaining.short_description = 'Time Remaining'
    
    def reset_attempts(self, request, queryset):
        """Admin action to reset attempt counts and unblock"""
        count = 0
        for rate_limit in queryset:
            rate_limit.reset_attempts()
            count += 1
        
        self.message_user(request, f"Reset {count} rate limit record(s).")
        logger.info(f"Admin {request.user.username} reset {count} rate limit records")
    reset_attempts.short_description = "Reset attempts"
    
    def block_selected(self, request, queryset):
        """Admin action to manually block selected records"""
        # Block for 24 hours
        blocked_until = timezone.now() + timezone.timedelta(hours=24)
        updated = queryset.update(blocked_until=blocked_until)
        
        self.message_user(request, f"Blocked {updated} record(s) for 24 hours.")
        logger.info(f"Admin {request.user.username} manually blocked {updated} rate limit records")
    block_selected.short_description = "Block for 24 hours"
    
    def unblock_selected(self, request, queryset):
        """Admin action to unblock selected records"""
        updated = queryset.update(blocked_until=None)
        
        self.message_user(request, f"Unblocked {updated} record(s).")
        logger.info(f"Admin {request.user.username} unblocked {updated} rate limit records")
    unblock_selected.short_description = "Unblock"
    
    def get_queryset(self, request):
        """Add annotations for better list display"""
        return super().get_queryset(request).select_related()
    
    class Media:
        """Add custom CSS for admin styling"""
        css = {
            'all': ('admin/css/custom_admin.css',)
        }


# ============================================================================
# ADDITIONAL ADMIN CONFIGURATIONS
# ============================================================================

# Customize admin site headers
admin.site.site_header = 'NetLog Administration'
admin.site.site_title = 'NetLog Admin'
admin.site.index_title = 'NetLog Management Console'


# Optional: Add dashboard widgets or summary views
class AdminDashboard:
    """
    Helper class for admin dashboard statistics.
    Can be used in custom admin templates.
    """
    
    @staticmethod
    def get_stats():
        """Get summary statistics for admin dashboard"""
        from django.contrib.auth.models import User
        
        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)
        last_7d = now - timezone.timedelta(days=7)
        
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'verified_users': Profile.objects.filter(email_verified=True).count(),
            'new_users_24h': User.objects.filter(date_joined__gte=last_24h).count(),
            'new_users_7d': User.objects.filter(date_joined__gte=last_7d).count(),
            'blocked_ips': RateLimit.objects.filter(
                blocked_until__gt=now
            ).count(),
            'total_rate_limits': RateLimit.objects.count(),
            'profiles_with_pending_verification': Profile.objects.filter(
                email_verified=False,
                email_verification_token__isnull=False
            ).count(),
        }
        
        # Calculate verification rate
        if stats['total_users'] > 0:
            stats['verification_rate'] = round(
                (stats['verified_users'] / stats['total_users']) * 100, 1
            )
        else:
            stats['verification_rate'] = 0
        
        return stats


# Optional: Add custom admin views
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def admin_dashboard_view(request):
    """
    Custom admin dashboard view with statistics.
    """
    stats = AdminDashboard.get_stats()
    
    # Get recent rate limit events
    recent_rate_limits = RateLimit.objects.order_by('-last_attempt_at')[:10]
    
    # Get users with multiple failed attempts
    suspicious_users = RateLimit.objects.filter(
        attempt_count__gte=2,
        blocked_until__isnull=False
    ).select_related()[:10]
    
    context = {
        'stats': stats,
        'recent_rate_limits': recent_rate_limits,
        'suspicious_users': suspicious_users,
        'title': 'Dashboard',
    }
    
    return render(request, 'admin/accounts/dashboard.html', context)


# Register custom admin views if needed
from django.urls import path

def get_admin_urls():
    """Add custom admin URLs"""
    urls = [
        path('dashboard/', admin_dashboard_view, name='accounts_dashboard'),
    ]
    return urls

# Uncomment to add custom URLs to admin
# admin.site.get_urls = get_admin_urls