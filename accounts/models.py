# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organization = models.CharField(max_length=150, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    token_created_at = models.DateTimeField(blank=True, null=True)
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_token_created_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

    def generate_verification_token(self):
        self.email_verification_token = secrets.token_urlsafe(32)
        self.token_created_at = timezone.now()
        self.save()
        return self.email_verification_token

    def is_token_valid(self):
        if not self.token_created_at:
            return False
        # Token expires after 24 hours
        expiry_time = self.token_created_at + timezone.timedelta(hours=24)
        return timezone.now() <= expiry_time
    
    def generate_password_reset_token(self):
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_token_created_at = timezone.now()
        self.save()
        return self.password_reset_token
    
    def is_password_reset_token_valid(self):
        if not self.password_reset_token_created_at:
            return False
        # Token expires after 1 hour (configurable)
        from django.conf import settings
        expiry_hours = getattr(settings, 'PASSWORD_RESET_TOKEN_EXPIRY_HOURS', 1)
        expiry_time = self.password_reset_token_created_at + timezone.timedelta(hours=expiry_hours)
        return timezone.now() <= expiry_time
    
    def clear_password_reset_token(self):
        self.password_reset_token = None
        self.password_reset_token_created_at = None
        self.save()


class RateLimit(models.Model):
    """Model to track rate limiting for various actions"""
    ACTION_CHOICES = [
        ('email_verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
        ('login', 'Login Attempt'),
        ('registration', 'Registration Attempt'),
    ]
    
    email = models.EmailField(db_index=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    attempt_count = models.PositiveIntegerField(default=0)
    first_attempt_at = models.DateTimeField(auto_now_add=True)
    last_attempt_at = models.DateTimeField(auto_now=True)
    blocked_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['email', 'action']
        indexes = [
            models.Index(fields=['email', 'action', 'blocked_until']),
        ]
    
    def __str__(self):
        return f"{self.email} - {self.action} - {self.attempt_count} attempts"
    
    def is_blocked(self):
        """Check if this email/action combination is currently blocked"""
        if not self.blocked_until:
            return False
        return timezone.now() < self.blocked_until
    
    def increment_attempt(self):
        """Increment attempt count and check if should be blocked"""
        self.attempt_count += 1
        self.last_attempt_at = timezone.now()
        
        # If this is the first attempt, set first_attempt_at
        if self.attempt_count == 1:
            self.first_attempt_at = timezone.now()
        
        # Check if we've exceeded the limit (3 attempts)
        if self.attempt_count >= 3:
            # Block for 1 hour
            self.blocked_until = timezone.now() + timezone.timedelta(hours=1)
        
        self.save()
        
    def reset_attempts(self):
        """Reset attempt count and unblock"""
        self.attempt_count = 0
        self.blocked_until = None
        self.first_attempt_at = timezone.now()
        self.save()
    
    @classmethod
    def check_rate_limit(cls, email, action):
        """
        Check if an action is rate limited.
        Returns (is_allowed, block_info) tuple.
        """
        rate_limit, created = cls.objects.get_or_create(
            email=email,
            action=action,
            defaults={
                'attempt_count': 0,
                'first_attempt_at': timezone.now()
            }
        )
        
        # Check if currently blocked
        if rate_limit.is_blocked():
            time_remaining = rate_limit.blocked_until - timezone.now()
            minutes_remaining = int(time_remaining.total_seconds() / 60)
            return False, {
                'blocked_until': rate_limit.blocked_until,
                'minutes_remaining': minutes_remaining,
                'attempts': rate_limit.attempt_count
            }
        
        # Check if we should reset the counter (if more than 1 hour has passed since first attempt)
        time_since_first = timezone.now() - rate_limit.first_attempt_at
        if time_since_first.total_seconds() > 3600:  # 1 hour
            rate_limit.reset_attempts()
        
        return True, {
            'attempts': rate_limit.attempt_count,
            'remaining_attempts': max(0, 3 - rate_limit.attempt_count)
        }