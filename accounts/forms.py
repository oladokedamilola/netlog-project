# accounts/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.validators import EmailValidator
from .models import Profile

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email'
    }))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter password'
    }))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Confirm password'
    }))

    class Meta:
        model = User
        fields = ["email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]  # Set username to email
        user.is_active = False  # Deactivate account until email is verified
        if commit:
            user.save()
            # Create profile with verification token
            profile, created = Profile.objects.get_or_create(user=user)
            profile.generate_verification_token()
        return user

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Optional: Add additional email validation
        return email

class SetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        })
    )
    new_password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("Passwords don't match")
            
            # Add password strength validation
            if len(password1) < 8:
                raise forms.ValidationError("Password must be at least 8 characters long")
            
            if password1.isdigit():
                raise forms.ValidationError("Password can't be entirely numeric")
        
        return cleaned_data
    
    
class UserProfileForm(forms.ModelForm):
    """Form for editing user profile information"""
    first_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email read-only? Optional - remove if you want users to change email
        # self.fields['email'].widget.attrs['readonly'] = True
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # If email is being changed, check if it's already taken
        if self.instance.email != email:
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError("This email is already in use.")
        return email

class ProfileSettingsForm(forms.ModelForm):
    """Form for editing profile settings"""
    organization = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your organization name'
        })
    )
    
    class Meta:
        model = Profile
        fields = ['organization']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['organization'].label = "Organization (Optional)"

class UserAvatarForm(forms.Form):
    """Form for uploading avatar (placeholder for future implementation)"""
    avatar = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )