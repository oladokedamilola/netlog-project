# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile
from django import forms
from django.contrib.auth.forms import UserCreationForm

# Inline admin for Profile
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('organization', 'created_at')
    readonly_fields = ('created_at',)

# Extend User Admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'profile_organization', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'profile__organization')
    ordering = ('-date_joined',)
    
    def profile_organization(self, obj):
        try:
            return obj.profile.organization
        except Profile.DoesNotExist:
            return "Not set"
    profile_organization.short_description = 'Organization'
    
    # Add organization to fieldsets in change form
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj:
            fieldsets = list(fieldsets)
            # Add organization to personal info section
            fieldsets[1] = ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'organization_display')})
        return fieldsets
    
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj:
            readonly_fields = readonly_fields + ('organization_display',)
        return readonly_fields
    
    def organization_display(self, obj):
        try:
            return obj.profile.organization
        except Profile.DoesNotExist:
            return "Not set"
    organization_display.short_description = 'Organization'

# Profile Admin (standalone)
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'created_at')
    list_filter = ('created_at', 'organization')
    search_fields = ('user__username', 'user__email', 'organization')
    readonly_fields = ('created_at',)
    fields = ('user', 'organization', 'created_at')
    ordering = ('-created_at',)
    
    # Auto-create profile if it doesn't exist
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            # Ensure profile doesn't already exist for this user
            if Profile.objects.filter(user=obj.user).exists():
                raise ValueError(f"Profile already exists for user {obj.user.username}")
        super().save_model(request, obj, form, change)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Additional customizations
class UserCreationFormExtended(UserCreationForm):
    organization = forms.CharField(max_length=150, required=False, help_text="User's organization")
    
    class Meta:
        model = User
        fields = ('username', 'email', 'organization')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Create profile with organization
            Profile.objects.create(user=user, organization=self.cleaned_data.get('organization'))
        return user

# If you want to use custom forms for UserAdmin
UserAdmin.add_form = UserCreationFormExtended
UserAdmin.add_fieldsets = (
    (None, {
        'classes': ('wide',),
        'fields': ('username', 'email', 'password1', 'password2', 'organization'),
    }),
)